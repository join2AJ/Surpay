package com.surpay.app.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.surpay.app.data.Coverage
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
    data class SignedIn(val profile: Profile, val isNewUser: Boolean = false) : SessionState
}

data class FormState(val busy: Boolean = false, val error: String? = null)

data class MatchesState(
    val loading: Boolean = false,
    val data: MatchesResponse? = null,
    val error: String? = null,
    val claimingRecordId: Int? = null,
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
                repo.restoreSession()?.let { SessionState.SignedIn(it) } ?: SessionState.SignedOut
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

    fun saveProfile(update: ProfileUpdate, onSaved: () -> Unit) = submit {
        val profile = repo.updateProfile(update)
        _session.value = SessionState.SignedIn(profile)
        refreshMatches()
        onSaved()
    }

    fun logout() {
        viewModelScope.launch {
            repo.logout()
            _matches.value = MatchesState()
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

    fun startClaim(recordId: Int) {
        if (_matches.value.claimingRecordId != null) return
        _matches.update { it.copy(claimingRecordId = recordId, error = null) }
        viewModelScope.launch {
            try {
                val claim = repo.startClaim(recordId)
                _matches.update { s ->
                    s.copy(
                        claimingRecordId = null,
                        data = s.data?.copy(matches = s.data.matches.map {
                            if (it.recordId == recordId) it.copy(claimStatus = claim.status) else it
                        }),
                    )
                }
            } catch (e: Exception) {
                _matches.update { it.copy(claimingRecordId = null, error = e.userMessage()) }
            }
        }
    }
}
