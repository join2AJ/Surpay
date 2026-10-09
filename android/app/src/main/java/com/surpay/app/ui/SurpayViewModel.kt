package com.surpay.app.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.surpay.app.data.AgreementDoc
import com.surpay.app.data.AppNotification
import com.surpay.app.data.AppPrefs
import com.surpay.app.data.Chat
import com.surpay.app.data.Policies
import com.surpay.app.data.Relative
import com.surpay.app.data.RelativeRequest
import com.surpay.app.data.AttorneyApplication
import com.surpay.app.data.AttorneyCase
import com.surpay.app.data.AttorneyProfile
import com.surpay.app.data.AttorneyTerms
import com.surpay.app.data.Claim
import com.surpay.app.data.Coverage
import com.surpay.app.data.IdentityRequest
import com.surpay.app.data.MatchPreview
import com.surpay.app.data.MatchesResponse
import com.surpay.app.data.Profile
import com.surpay.app.data.ProfileUpdate
import com.surpay.app.data.ServerStore
import com.surpay.app.data.SurpayRepository
import com.surpay.app.data.userMessage
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

sealed interface SessionState {
    data object Loading : SessionState
    data object SignedOut : SessionState
    data class Unreachable(val message: String) : SessionState
    data class SignedIn(
        val profile: Profile,
        val isNewUser: Boolean = false,
        /** Signed in to the on-device demo because no server was reachable. */
        val offlineDemo: Boolean = false,
    ) : SessionState
}

data class FormState(val busy: Boolean = false, val error: String? = null)

data class MatchesState(
    val loading: Boolean = false,
    val data: MatchesResponse? = null,
    val error: String? = null,
)

/** First-run intro and "what's new" after an update. */
data class AppStart(val loaded: Boolean = false, val showIntro: Boolean = false, val whatsNewFrom: Int? = null,
                    val developer: Boolean = false)

class SurpayViewModel(
    private val repo: SurpayRepository,
    private val server: ServerStore,
    /** null in tests that don't exercise the intro: treated as already seen. */
    private val prefs: AppPrefs? = null,
    private val versionCode: Int = 0,
    /** Installed over an older version (not a fresh install): show "what's new". */
    private val isUpdate: Boolean = false,
) : ViewModel() {
    private val _start = MutableStateFlow(AppStart(loaded = prefs == null))
    val start: StateFlow<AppStart> = _start.asStateFlow()
    private val _session = MutableStateFlow<SessionState>(SessionState.Loading)
    val session: StateFlow<SessionState> = _session.asStateFlow()

    private val _form = MutableStateFlow(FormState())
    val form: StateFlow<FormState> = _form.asStateFlow()

    private val _matches = MutableStateFlow(MatchesState())
    val matches: StateFlow<MatchesState> = _matches.asStateFlow()

    private val _coverage = MutableStateFlow<Coverage?>(null)
    val coverage: StateFlow<Coverage?> = _coverage.asStateFlow()

    private val _serverUrl = MutableStateFlow(server.current)
    val serverUrl: StateFlow<String> = _serverUrl.asStateFlow()

    init {
        viewModelScope.launch {
            prefs?.let { p ->
                val introSeen = p.introSeen()
                val seenVersion = p.whatsNewSeen()
                val showWhatsNew = (introSeen || isUpdate) && seenVersion < versionCode
                if (!showWhatsNew) p.setWhatsNewSeen(versionCode)  // a fresh install gets the intro instead
                _start.value = AppStart(
                    loaded = true, showIntro = !introSeen,
                    whatsNewFrom = seenVersion.takeIf { showWhatsNew },
                    developer = p.developer(),
                )
            }
            _serverUrl.value = server.load()
            loadCoverage()
            restoreSession()
        }
    }

    fun finishIntro() {
        _start.update { it.copy(showIntro = false) }
        viewModelScope.launch { prefs?.setIntroSeen() }
    }

    fun dismissWhatsNew() {
        _start.update { it.copy(whatsNewFrom = null) }
        viewModelScope.launch { prefs?.setWhatsNewSeen(versionCode) }
    }

    /** Tester options (server address): tap the logo 7 times. */
    fun unlockDeveloper() {
        _start.update { it.copy(developer = true) }
        viewModelScope.launch { prefs?.setDeveloper(true) }
    }

    private fun loadCoverage() {
        viewModelScope.launch { _coverage.value = runCatching { repo.coverage() }.getOrNull() }
    }

    fun restoreSession() {
        _session.value = SessionState.Loading
        viewModelScope.launch {
            _session.value = try {
                repo.restoreSession()?.let { SessionState.SignedIn(it, offlineDemo = repo.isOfflineDemo) }
                    ?: SessionState.SignedOut
            } catch (e: Exception) {
                SessionState.Unreachable(e.userMessage())
            }
        }
    }

    /** Point the app at a different server. Accounts don't carry over, so this signs out. */
    fun setServerUrl(url: String) {
        viewModelScope.launch {
            server.save(url)
            _serverUrl.value = server.current
            repo.logout()
            _matches.value = MatchesState()
            _claims.value = null
            _coverage.value = null
            _form.value = FormState()
            _session.value = SessionState.SignedOut
            loadCoverage()
        }
    }

    private fun submit(block: suspend () -> Unit) {
        if (_form.value.busy) return
        _form.value = FormState(busy = true)
        viewModelScope.launch {
            try {
                block()
                _form.value = FormState()
            } catch (e: Exception) {
                if (sessionExpired(e)) return@launch
                _form.value = FormState(error = e.userMessage())
            }
        }
    }

    /** Signed out elsewhere (password changed, "sign out everywhere", account closed): go back to sign-in. */
    private fun sessionExpired(e: Throwable): Boolean {
        val expired = e is retrofit2.HttpException && e.code() == 401 && _session.value is SessionState.SignedIn
        if (expired) {
            logout()
            _form.value = FormState(error = "You've been signed out. Please sign in again.")
        }
        return expired
    }

    /** Bumped on sign-out so answers to requests sent before it are dropped, not shown to the next user. */
    @Volatile private var generation = 0

    fun clearFormError() = _form.update { it.copy(error = null) }

    fun signup(email: String, password: String, fullName: String, role: String = "claimant", acceptTerms: Boolean = true) = submit {
        val profile = repo.signup(email, password, fullName, role, acceptTerms)
        _session.value = SessionState.SignedIn(profile, isNewUser = true)
    }

    fun login(email: String, password: String) = submit {
        _session.value = SessionState.SignedIn(repo.login(email, password))
    }

    fun demoLogin() = submit {
        val profile = repo.demoLogin()
        _session.value = SessionState.SignedIn(profile, offlineDemo = repo.isOfflineDemo)
    }

    fun demoAttorneyLogin() = submit {
        _session.value = SessionState.SignedIn(repo.demoAttorneyLogin())
    }

    fun saveProfile(update: ProfileUpdate, onSaved: () -> Unit) = submit {
        val profile = repo.updateProfile(update)
        _session.value = SessionState.SignedIn(profile, offlineDemo = repo.isOfflineDemo)
        if (profile.identityStatus == "approved") refreshMatches() else refreshPreview()
        onSaved()
    }

    fun logout() {
        generation++
        viewModelScope.launch {
            repo.logout()
            prefs?.setLastNotification(0)
            _preview.value = null
            _agreement.value = null
            _terms.value = null
            _matches.value = MatchesState()
            _claims.value = null
            _attorney.value = AttorneyState()
            _cases.value = null
            _documents.value = emptyMap()
            _chats.value = emptyMap()
            _notifications.value = null
            _relatives.value = null
            _session.value = SessionState.SignedOut
        }
    }

    fun refreshMatches() {
        _matches.update { it.copy(loading = true, error = null) }
        val gen = generation
        viewModelScope.launch {
            try {
                val data = repo.matches()
                if (gen == generation) _matches.update { it.copy(loading = false, data = data) }
            } catch (e: Exception) {
                if (!sessionExpired(e)) _matches.update { it.copy(loading = false, error = e.userMessage()) }
            }
        }
    }

    // --- Claims ------------------------------------------------------------------------------

    private val _claims = MutableStateFlow<List<Claim>?>(null)
    /** The signed-in person's claims, newest first; null until loaded. */
    val claims: StateFlow<List<Claim>?> = _claims.asStateFlow()

    private val _agreement = MutableStateFlow<AgreementDoc?>(null)
    val agreement: StateFlow<AgreementDoc?> = _agreement.asStateFlow()

    fun refreshClaims() {
        val gen = generation
        viewModelScope.launch {
            runCatching { repo.claims() }
                .onSuccess { if (gen == generation) _claims.value = it }
                .onFailure { sessionExpired(it) }
        }
    }

    /** The client's right to a different attorney before the claim is filed. */
    fun changeAttorney(claimId: Int) = submit { upsertClaims(listOf(repo.changeAttorney(claimId))) }

    fun changePassword(current: String, new: String, onDone: () -> Unit) = submit {
        val profile = repo.changePassword(current, new)
        (_session.value as? SessionState.SignedIn)?.let { _session.value = it.copy(profile = profile) }
        onDone()
    }

    private fun upsertClaims(updated: List<Claim>) {
        val byId = (_claims.value ?: emptyList()).associateBy { it.id }.toMutableMap()
        updated.forEach { byId[it.id] = it }
        _claims.value = byId.values.sortedByDescending { it.createdAt }
        // Match cards show the claim status too.
        _matches.update { s ->
            s.copy(data = s.data?.copy(matches = s.data.matches.map { m ->
                updated.firstOrNull { it.recordId == m.recordId }?.let { m.copy(claimStatus = it.status) } ?: m
            }))
        }
    }

    /** Start (or reopen) the claim for a match and hand it to [onReady] to continue the flow. */
    fun startClaim(recordId: Int, onReady: (Claim) -> Unit) = submit {
        val claim = repo.startClaim(recordId)
        upsertClaims(listOf(claim))
        onReady(claim)
    }

    fun reloadClaim(id: Int) {
        viewModelScope.launch {
            runCatching { repo.claim(id) }.onSuccess { upsertClaims(listOf(it)) }
        }
    }

    fun submitIdentity(body: IdentityRequest, onDone: () -> Unit = {}) = submit {
        upsertClaims(repo.submitIdentity(body))
        refreshProfileNow()
        onDone()
    }

    private suspend fun refreshProfileNow() {
        val profile = repo.me()
        val current = _session.value as? SessionState.SignedIn ?: return
        _session.value = current.copy(profile = profile, offlineDemo = repo.isOfflineDemo)
    }

    /** Re-read the profile, e.g. to see whether staff have approved the ID yet. */
    fun refreshProfile() {
        viewModelScope.launch { runCatching { refreshProfileNow() } }
    }

    private val _preview = MutableStateFlow<MatchPreview?>(null)
    /** While ID is under review: how many possible records (no amounts or details). */
    val preview: StateFlow<MatchPreview?> = _preview.asStateFlow()

    fun refreshPreview() {
        viewModelScope.launch { runCatching { repo.matchesPreview() }.onSuccess { _preview.value = it } }
    }

    fun loadAgreement(claimId: Int) {
        _agreement.value = null
        viewModelScope.launch {
            try {
                _agreement.value = repo.agreement(claimId)
            } catch (e: Exception) {
                _form.value = FormState(error = e.userMessage())
            }
        }
    }

    fun signAgreement(claimId: Int, name: String, signaturePng: ByteArray, onDone: () -> Unit) = submit {
        upsertClaims(listOf(repo.signAgreement(claimId, name, signaturePng)))
        onDone()
    }


    // --- Messages with the attorney (claimant side and attorney side) ---------------------------

    private val _chats = MutableStateFlow<Map<Int, Chat>>(emptyMap())
    /** claim/case id -> conversation. */
    val chats: StateFlow<Map<Int, Chat>> = _chats.asStateFlow()

    private fun isAttorney() = (_session.value as? SessionState.SignedIn)?.profile?.role == "attorney"

    fun loadChat(id: Int) {
        val gen = generation
        viewModelScope.launch {
            runCatching { if (isAttorney()) repo.caseMessages(id) else repo.messages(id) }
                .onSuccess { c -> if (gen == generation) _chats.update { it + (id to c) } }
                .onFailure { sessionExpired(it) }
        }
    }

    fun sendMessage(id: Int, body: String, onSent: () -> Unit) = submit {
        val chat = if (isAttorney()) repo.sendCaseMessage(id, body) else repo.sendMessage(id, body)
        _chats.update { it + (id to chat) }
        onSent()
    }

    // --- Notifications ----------------------------------------------------------------------------

    private val _notifications = MutableStateFlow<List<AppNotification>?>(null)
    val notifications: StateFlow<List<AppNotification>?> = _notifications.asStateFlow()

    fun loadNotifications() {
        viewModelScope.launch { runCatching { repo.notifications() }.onSuccess { _notifications.value = it.items } }
    }

    fun markNotificationsRead() {
        viewModelScope.launch {
            runCatching { repo.markNotificationsRead() }
            _notifications.update { list -> list?.map { it.copy(read = true) } }
            runCatching { refreshProfileNow() }
        }
    }

    // --- Policies, family members, privacy rights ------------------------------------------------

    private val _policies = MutableStateFlow<Policies?>(null)
    val policies: StateFlow<Policies?> = _policies.asStateFlow()

    fun loadPolicies() {
        if (_policies.value != null) return
        viewModelScope.launch { runCatching { repo.policies() }.onSuccess { _policies.value = it } }
    }

    fun acceptCurrentTerms() = submit {
        repo.acceptCurrentTerms()
        refreshProfileNow()
    }

    private val _relatives = MutableStateFlow<List<Relative>?>(null)
    val relatives: StateFlow<List<Relative>?> = _relatives.asStateFlow()

    fun loadRelatives() {
        viewModelScope.launch { runCatching { repo.relatives() }.onSuccess { _relatives.value = it } }
    }

    fun addRelative(body: RelativeRequest, onDone: () -> Unit) = submit {
        val r = repo.addRelative(body)
        _relatives.update { (it ?: emptyList()) + r }
        onDone()
    }

    fun removeRelative(id: Int) = submit {
        repo.removeRelative(id)
        _relatives.update { list -> list?.filterNot { it.id == id } }
    }

    /** Everything Surpay holds about the person, as JSON, for [onReady] to save or share. */
    fun exportData(onReady: (ByteArray) -> Unit) = submit { onReady(repo.exportData()) }

    fun deleteAccount(onDone: (String) -> Unit) = submit {
        val r = repo.deleteAccount()
        onDone(r.message)
        logout()
    }

    fun logoutEverywhere() = submit {
        repo.logoutEverywhere()
        logout()
    }

    // --- Counties for the address form ------------------------------------------------------

    private val _counties = MutableStateFlow<Map<String, List<String>>>(emptyMap())
    /** State code -> county names. A state missing here hasn't loaded (or failed to). */
    val counties: StateFlow<Map<String, List<String>>> = _counties.asStateFlow()

    fun loadCounties(state: String) {
        if (state.isBlank() || _counties.value[state]?.isNotEmpty() == true) return
        viewModelScope.launch {
            runCatching { repo.counties(state) }.onSuccess { list ->
                if (list.isNotEmpty()) _counties.update { it + (state to list) }
            }
        }
    }

    // --- Partner attorneys ------------------------------------------------------------------

    /** Loaded = false until first fetched; profile null = hasn't applied yet. */
    data class AttorneyState(val loaded: Boolean = false, val profile: AttorneyProfile? = null, val error: String? = null)

    private val _attorney = MutableStateFlow(AttorneyState())
    val attorney: StateFlow<AttorneyState> = _attorney.asStateFlow()

    private val _cases = MutableStateFlow<List<AttorneyCase>?>(null)
    val cases: StateFlow<List<AttorneyCase>?> = _cases.asStateFlow()

    private val _terms = MutableStateFlow<AttorneyTerms?>(null)
    val terms: StateFlow<AttorneyTerms?> = _terms.asStateFlow()

    private val _documents = MutableStateFlow<Map<String, ByteArray>>(emptyMap())
    /** "caseId/kind" -> image bytes, for accepted cases. */
    val documents: StateFlow<Map<String, ByteArray>> = _documents.asStateFlow()

    fun loadAttorney() {
        viewModelScope.launch {
            _attorney.value = try {
                AttorneyState(loaded = true, profile = repo.attorneyMe())
            } catch (e: Exception) {
                _attorney.value.copy(loaded = true, error = e.userMessage())
            }
        }
    }

    fun loadTerms(state: String) {
        viewModelScope.launch { runCatching { repo.attorneyTerms(state) }.onSuccess { _terms.value = it } }
    }

    fun applyAsAttorney(body: AttorneyApplication) = submit {
        _attorney.value = AttorneyState(loaded = true, profile = repo.attorneyApply(body))
    }

    fun loadCases() {
        val gen = generation
        viewModelScope.launch {
            try {
                repo.attorneyCases().let { if (gen == generation) _cases.value = it }
            } catch (e: Exception) {
                if (!sessionExpired(e)) _form.value = FormState(error = e.userMessage())
            }
        }
    }

    private fun replaceCase(c: AttorneyCase) {
        _cases.update { list -> (list ?: emptyList()).map { if (it.id == c.id) c else it }.let { if (it.none { x -> x.id == c.id }) it + c else it } }
    }

    fun reloadCase(id: Int) {
        viewModelScope.launch { runCatching { repo.attorneyCase(id) }.onSuccess { replaceCase(it) } }
    }

    fun acceptCase(id: Int) = submit { replaceCase(repo.acceptCase(id)) }

    fun declineCase(id: Int, reason: String, onDone: () -> Unit) = submit {
        repo.declineCase(id, reason)
        _cases.update { list -> list?.filterNot { it.id == id } }
        onDone()
    }

    fun updateCase(id: Int, status: String, note: String) = submit { replaceCase(repo.updateCase(id, status, note)) }

    /** The printable claim packet (PDF) for an accepted case. */
    fun downloadPacket(caseId: Int, onReady: (ByteArray) -> Unit) = submit { onReady(repo.casePacket(caseId)) }

    fun loadDocument(caseId: Int, kind: String) {
        val key = "$caseId/$kind"
        if (key in _documents.value) return
        viewModelScope.launch {
            runCatching { repo.caseDocument(caseId, kind) }.onSuccess { bytes -> _documents.update { it + (key to bytes) } }
        }
    }
}
