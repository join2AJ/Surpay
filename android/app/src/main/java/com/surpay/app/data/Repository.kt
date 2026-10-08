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

    suspend fun signup(email: String, password: String, fullName: String): Profile =
        api.signup(SignupRequest(email.trim(), password, fullName.trim())).also { tokens.save(it.token) }.user

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

    suspend fun logout() {
        tokens.clear()
        isOfflineDemo = false
    }

    suspend fun updateProfile(update: ProfileUpdate): Profile = api.updateMe(update)
    suspend fun matches(): MatchesResponse = api.matches()
    suspend fun startClaim(recordId: Int): Claim = api.startClaim(ClaimRequest(recordId))
    suspend fun claims(): List<Claim> = api.claims()
    suspend fun claim(id: Int): Claim = api.claim(id)
    suspend fun submitIdentity(body: IdentityRequest): List<Claim> = api.submitIdentity(body)
    suspend fun agreement(claimId: Int): AgreementDoc = api.agreement(claimId)
    suspend fun signAgreement(claimId: Int, name: String): Claim = api.signAgreement(claimId, SignRequest(name, true))
    suspend fun counties(state: String): List<String> = api.counties(state)
    suspend fun coverage(): Coverage = remote.coverage()
}

/** The server isn't there: unreachable, or a host that has no Surpay API behind it. */
private fun Exception.isNoServer(): Boolean = this is IOException ||
    (this is HttpException && (code() == 404 || code() >= 500))

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
            code() == 404 -> "No Surpay server found at this address. Deploy the backend (docs/DEPLOY.md) " +
                "or change the address under Server settings."
            else -> "Something went wrong (error ${code()}). Please try again."
        }
    }
    is IOException -> "Can't reach Surpay. Check your internet connection and try again."
    else -> message ?: "Something went wrong. Please try again."
}
