package com.surpay.app.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.first
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import retrofit2.HttpException
import java.io.IOException

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "surpay")
private val TOKEN = stringPreferencesKey("token")
private val SERVER_URL = stringPreferencesKey("server_url")
private val INTRO_SEEN = androidx.datastore.preferences.core.booleanPreferencesKey("intro_seen")
private val WHATS_NEW_SEEN = androidx.datastore.preferences.core.intPreferencesKey("whats_new_seen")
private val LAST_NOTIFICATION = androidx.datastore.preferences.core.intPreferencesKey("last_notification")
private val DEVELOPER = androidx.datastore.preferences.core.booleanPreferencesKey("developer")

/** Small app settings: first-run intro, "what's new" per version, notification bookmark. */
class AppPrefs(private val context: Context) {
    suspend fun introSeen(): Boolean = context.dataStore.data.first()[INTRO_SEEN] ?: false
    suspend fun setIntroSeen() { context.dataStore.edit { it[INTRO_SEEN] = true } }

    /** Version code whose "what's new" the person has seen (0 = never). */
    suspend fun whatsNewSeen(): Int = context.dataStore.data.first()[WHATS_NEW_SEEN] ?: 0
    suspend fun setWhatsNewSeen(version: Int) { context.dataStore.edit { it[WHATS_NEW_SEEN] = version } }

    /** Newest notification already shown on the phone. */
    suspend fun lastNotification(): Int = context.dataStore.data.first()[LAST_NOTIFICATION] ?: 0
    suspend fun setLastNotification(id: Int) { context.dataStore.edit { it[LAST_NOTIFICATION] = id } }

    /** Hidden tester options (server address), unlocked by tapping the logo 7 times. */
    suspend fun developer(): Boolean = context.dataStore.data.first()[DEVELOPER] ?: false
    suspend fun setDeveloper(on: Boolean) { context.dataStore.edit { it[DEVELOPER] = on } }
}

/** This install's identity for the audit trail: a random install ID plus Android's per-app device ID. */
@android.annotation.SuppressLint("HardwareIds")
fun deviceInfo(context: Context, appVersion: String): DeviceInfo {
    val prefs = context.getSharedPreferences("surpay_device", Context.MODE_PRIVATE)
    val install = prefs.getString("install_id", null) ?: java.util.UUID.randomUUID().toString().also {
        prefs.edit().putString("install_id", it).apply()
    }
    val androidId = runCatching {
        android.provider.Settings.Secure.getString(context.contentResolver, android.provider.Settings.Secure.ANDROID_ID)
    }.getOrNull().orEmpty()
    return DeviceInfo(
        deviceId = androidId, installId = install,
        model = "${android.os.Build.MANUFACTURER} ${android.os.Build.MODEL}".trim(),
        osVersion = "Android ${android.os.Build.VERSION.RELEASE}", appVersion = appVersion,
    )
}

/** Which Surpay server the app talks to. Defaults to the URL baked in at build time. */
class ServerStore(private val context: Context, private val defaultUrl: String) {
    @Volatile var current: String = defaultUrl
        private set

    suspend fun load(): String = (context.dataStore.data.first()[SERVER_URL] ?: defaultUrl).also { current = it }

    suspend fun save(url: String) {
        val clean = url.trim().let { if (it.endsWith("/")) it else "$it/" }
        context.dataStore.edit { if (clean == defaultUrl) it.remove(SERVER_URL) else it[SERVER_URL] = clean }
        current = clean
    }
}

/** Stores the sign-in token on the device. */
class TokenStore(private val context: Context) {
    @Volatile var cached: String? = null
        private set

    suspend fun load(): String? = context.dataStore.data.first()[TOKEN].also { cached = it }

    suspend fun save(token: String) {
        context.dataStore.edit { it[TOKEN] = token }
        cached = token
    }

    suspend fun clear() {
        context.dataStore.edit { it.remove(TOKEN) }
        cached = null
    }
}

class SurpayRepository(private val remote: SurpayApi, private val tokens: TokenStore) {
    private val offlineDemo = OfflineDemoApi()

    /** True while signed in to the on-device demo because no server was reachable. */
    @Volatile var isOfflineDemo = false
        private set

    private val api: SurpayApi get() = if (isOfflineDemo) offlineDemo else remote

    suspend fun restoreSession(): Profile? {
        val token = tokens.load() ?: return null
        if (token == OfflineDemoApi.OFFLINE_DEMO_TOKEN) {
            isOfflineDemo = true
            return offlineDemo.me()
        }
        return try {
            remote.me()
        } catch (e: HttpException) {
            if (e.code() == 401) tokens.clear()
            null
        }
    }

    suspend fun signup(email: String, password: String, fullName: String, role: String = "claimant", acceptTerms: Boolean = true): Profile =
        api.signup(SignupRequest(email.trim(), password, fullName.trim(), role = role, acceptTerms = acceptTerms))
            .also { tokens.save(it.token) }.user

    suspend fun login(email: String, password: String): Profile =
        api.login(LoginRequest(email.trim(), password)).also { tokens.save(it.token) }.user

    /**
     * Testing only: the server's shared fictional account, reset on every demo sign-in. If there
     * is no Surpay server at the configured address (not deployed yet, or offline), fall back to
     * the same demo running on the phone so the app can still be tried.
     */
    suspend fun demoLogin(): Profile {
        val response = try {
            isOfflineDemo = false
            remote.demoLogin()
        } catch (e: Exception) {
            if (!e.isNoServer()) throw e
            isOfflineDemo = true
            offlineDemo.demoLogin()
        }
        tokens.save(response.token)
        return response.user
    }

    /** Testing only: the shared fictional attorney, approved, with one demo case offered. Needs the server. */
    suspend fun demoAttorneyLogin(): Profile {
        isOfflineDemo = false
        val response = try {
            remote.demoAttorneyLogin()
        } catch (e: Exception) {
            if (e.isNoServer()) throw IllegalStateException("The attorney demo needs the Surpay server. Try again in a minute.")
            throw e
        }
        tokens.save(response.token)
        return response.user
    }

    /** Testing only: a pass to the staff dashboard limited to demo data. */
    suspend fun demoAdminPass(): String = remote.demoAdmin().token

    suspend fun logout() {
        tokens.clear()
        isOfflineDemo = false
    }

    suspend fun updateProfile(update: ProfileUpdate): Profile = api.updateMe(update)
    suspend fun matches(): MatchesResponse = api.matches()
    suspend fun matchesPreview(): MatchPreview = api.matchesPreview()
    suspend fun me(): Profile = api.me()
    suspend fun startClaim(recordId: Int): Claim = api.startClaim(ClaimRequest(recordId))
    suspend fun claims(): List<Claim> = api.claims()
    suspend fun claim(id: Int): Claim = api.claim(id)
    suspend fun submitIdentity(body: IdentityRequest): List<Claim> = api.submitIdentity(body)
    suspend fun agreement(claimId: Int): AgreementDoc = api.agreement(claimId)
    suspend fun signAgreement(claimId: Int, name: String, signaturePng: ByteArray): Claim = api.signAgreement(
        claimId, SignRequest(name, true, java.util.Base64.getEncoder().encodeToString(signaturePng)))
    suspend fun messages(claimId: Int): Chat = api.messages(claimId)
    suspend fun sendMessage(claimId: Int, body: String): Chat = api.sendMessage(claimId, MessageRequest(body))
    suspend fun notifications(afterId: Int = 0): Notifications = api.notifications(afterId)
    suspend fun markNotificationsRead() { api.markNotificationsRead() }
    suspend fun policies(): Policies = remote.policies()
    suspend fun acceptCurrentTerms() { api.acceptCurrentTerms() }
    suspend fun relatives(): List<Relative> = api.relatives()
    suspend fun addRelative(body: RelativeRequest): Relative = api.addRelative(body)
    suspend fun removeRelative(id: Int) { api.removeRelative(id) }
    suspend fun exportData(): ByteArray = api.exportData().use { it.bytes() }
    suspend fun deleteAccount(): DeleteResult = api.deleteAccount().also { tokens.clear() }  // the server signs out every device either way
    suspend fun logoutEverywhere() {
        api.logoutEverywhere()
        tokens.clear()
        isOfflineDemo = false
    }
    suspend fun counties(state: String): List<String> = api.counties(state)

    // Attorneys always work against the real server.
    suspend fun attorneyTerms(state: String): AttorneyTerms = remote.attorneyTerms(state)
    suspend fun attorneyApply(body: AttorneyApplication): AttorneyProfile = remote.attorneyApply(body)
    /** null when they haven't applied yet. */
    suspend fun attorneyMe(): AttorneyProfile? = try {
        remote.attorneyMe()
    } catch (e: HttpException) {
        if (e.code() == 404) null else throw e
    }
    suspend fun attorneyCases(): List<AttorneyCase> = remote.attorneyCases()
    suspend fun attorneyCase(id: Int): AttorneyCase = remote.attorneyCase(id)
    suspend fun acceptCase(id: Int): AttorneyCase = remote.acceptCase(id, AcceptRequest(conflictChecked = true))
    suspend fun changeAttorney(claimId: Int): Claim = api.changeAttorney(claimId)
    suspend fun uploadDocument(claimId: Int, requestId: Int, jpeg: ByteArray): Claim =
        api.uploadDocument(claimId, requestId, DocumentUpload(java.util.Base64.getEncoder().encodeToString(jpeg)))
    suspend fun updateAttorney(body: AttorneyUpdate): AttorneyProfile = remote.updateAttorney(body)
    suspend fun requestDocument(caseId: Int, kind: String, note: String): AttorneyCase =
        remote.requestDocument(caseId, DocumentRequestBody(kind, note))
    suspend fun requestedFile(caseId: Int, requestId: Int): ByteArray = remote.requestedFile(caseId, requestId).use { it.bytes() }
    suspend fun reviewDocument(caseId: Int, requestId: Int, accept: Boolean, note: String): AttorneyCase =
        remote.reviewDocument(caseId, requestId, DocumentReview(if (accept) "accepted" else "rejected", note))
    /** New password; the server signs out other devices and returns a fresh token for this one. */
    suspend fun changePassword(current: String, new: String): Profile =
        remote.changePassword(PasswordChange(current, new)).also { tokens.save(it.token) }.user
    suspend fun declineCase(id: Int, reason: String) { remote.declineCase(id, DeclineRequest(reason)) }
    suspend fun updateCase(id: Int, status: String, note: String): AttorneyCase = remote.updateCase(id, CaseStatusRequest(status, note))
    suspend fun caseDocument(id: Int, kind: String): ByteArray = remote.caseDocument(id, kind).use { it.bytes() }
    suspend fun casePacket(id: Int): ByteArray = remote.casePacket(id).use { it.bytes() }
    suspend fun caseMessages(id: Int): Chat = remote.caseMessages(id)
    suspend fun sendCaseMessage(id: Int, body: String): Chat = remote.sendCaseMessage(id, MessageRequest(body))
    suspend fun coverage(): Coverage = remote.coverage()
}

/** The server isn't there: unreachable, or a host that has no Surpay API behind it. */
private fun Exception.isNoServer(): Boolean = this is IOException ||
    (this is HttpException && (code() >= 500 || (code() == 404 && !hasSurpayDetail())))

/** A Surpay server answers errors with JSON {"detail": ...}; a bare 404 means nothing is deployed there. */
private fun HttpException.hasSurpayDetail(): Boolean = runCatching {
    response()?.errorBody()?.source()?.peek()?.readUtf8()?.contains("\"detail\"") == true
}.getOrDefault(false)

/** Turn a network/HTTP failure into a sentence a person can act on. */
fun Throwable.userMessage(): String = when (this) {
    is HttpException -> {
        val detail = runCatching {
            val body = response()?.errorBody()?.string().orEmpty()
            when (val d = SurpayApi.json.decodeFromString<ApiError>(body).detail) {
                is JsonPrimitive -> d.contentOrNull
                // FastAPI validation errors: [{"msg": "...", "loc": [...]}, ...]
                is JsonArray -> d.mapNotNull { ((it as? JsonObject)?.get("msg") as? JsonPrimitive)?.contentOrNull }
                    .joinToString("\n")
                else -> null
            }
        }.getOrNull()
        when {
            !detail.isNullOrBlank() -> detail
            code() == 404 -> "Surpay isn't available right now. Please try again in a few minutes."
            code() == 429 -> "Too many attempts. Please wait 15 minutes and try again."
            else -> "Something went wrong (error ${code()}). Please try again."
        }
    }
    is IOException -> "Can't reach Surpay. Check your internet connection and try again."
    else -> message ?: "Something went wrong. Please try again."
}
