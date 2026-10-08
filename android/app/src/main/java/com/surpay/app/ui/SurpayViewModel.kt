package com.surpay.app.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.surpay.app.data.AgreementDoc
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

class SurpayViewModel(private val repo: SurpayRepository, private val server: ServerStore) : ViewModel() {
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
            _serverUrl.value = server.load()
            loadCoverage()
            restoreSession()
        }
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
                _form.value = FormState(error = e.userMessage())
            }
        }
    }

    fun clearFormError() = _form.update { it.copy(error = null) }

    fun signup(email: String, password: String, fullName: String) = submit {
        val profile = repo.signup(email, password, fullName)
        _session.value = SessionState.SignedIn(profile, isNewUser = true)
    }

    fun login(email: String, password: String) = submit {
        _session.value = SessionState.SignedIn(repo.login(email, password))
    }

    fun demoLogin() = submit {
        val profile = repo.demoLogin()
        _session.value = SessionState.SignedIn(profile, offlineDemo = repo.isOfflineDemo)
    }

    fun saveProfile(update: ProfileUpdate, onSaved: () -> Unit) = submit {
        val profile = repo.updateProfile(update)
        _session.value = SessionState.SignedIn(profile, offlineDemo = repo.isOfflineDemo)
        if (profile.identityStatus == "approved") refreshMatches() else refreshPreview()
        onSaved()
    }

    fun logout() {
        viewModelScope.launch {
            repo.logout()
            _matches.value = MatchesState()
            _claims.value = null
            _session.value = SessionState.SignedOut
        }
    }

    fun refreshMatches() {
        _matches.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try {
                val data = repo.matches()
                _matches.update { it.copy(loading = false, data = data) }
            } catch (e: Exception) {
                _matches.update { it.copy(loading = false, error = e.userMessage()) }
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
        viewModelScope.launch {
            runCatching { repo.claims() }.onSuccess { _claims.value = it }
        }
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

    fun signAgreement(claimId: Int, name: String, onDone: () -> Unit) = submit {
        upsertClaims(listOf(repo.signAgreement(claimId, name)))
        onDone()
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
}
