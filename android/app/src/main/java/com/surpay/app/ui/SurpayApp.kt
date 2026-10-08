package com.surpay.app.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.AttachMoney
import androidx.compose.material.icons.filled.Checklist
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.surpay.app.ui.screens.AgreementScreen
import com.surpay.app.ui.screens.AttorneyApplyScreen
import com.surpay.app.ui.screens.AttorneyPendingScreen
import com.surpay.app.ui.screens.CaseDetailScreen
import com.surpay.app.ui.screens.CasesScreen
import com.surpay.app.ui.screens.AuthScreen
import com.surpay.app.ui.screens.ClaimScreen
import com.surpay.app.ui.screens.ClaimsScreen
import com.surpay.app.ui.screens.IdentityScreen
import com.surpay.app.ui.screens.LoadingScreen
import com.surpay.app.ui.screens.OnboardingHeader
import com.surpay.app.ui.screens.VerifyingScreen
import com.surpay.app.ui.screens.ServerSettingsDialog
import com.surpay.app.ui.screens.UnreachableScreen
import com.surpay.app.ui.screens.MatchDetailScreen
import com.surpay.app.ui.screens.MatchesScreen
import com.surpay.app.ui.screens.ProfileScreen

private object Routes {
    const val SETUP = "setup"
    const val MATCHES = "matches"
    const val CLAIMS = "claims"
    const val PROFILE = "profile"
    const val DETAIL = "match/{id}"
    const val CLAIM = "claim/{id}"
    const val IDENTITY = "claim/{id}/identity"
    const val AGREEMENT = "claim/{id}/agreement"
    fun detail(id: Int) = "match/$id"
    fun claim(id: Int) = "claim/$id"
    fun identity(id: Int) = "claim/$id/identity"
    fun agreement(id: Int) = "claim/$id/agreement"
    val TABS = setOf(MATCHES, CLAIMS, PROFILE)
}

@Composable
fun SurpayApp(vm: SurpayViewModel) {
    val session by vm.session.collectAsStateWithLifecycle()
    val form by vm.form.collectAsStateWithLifecycle()
    val coverage by vm.coverage.collectAsStateWithLifecycle()
    val serverUrl by vm.serverUrl.collectAsStateWithLifecycle()
    var showServer by rememberSaveable { mutableStateOf(false) }

    when (val s = session) {
        SessionState.Loading -> LoadingScreen()
        is SessionState.Unreachable -> UnreachableScreen(
            message = s.message,
            serverUrl = serverUrl,
            onRetry = vm::restoreSession,
            onServerSettings = { showServer = true },
        )
        SessionState.SignedOut -> AuthScreen(
            form = form,
            coverage = coverage,
            onSignup = vm::signup,
            onLogin = vm::login,
            onDemoLogin = vm::demoLogin,
            onClearError = vm::clearFormError,
            onServerSettings = { showServer = true },
        )
        // Attorneys get their own app; verified claimants get theirs; everyone else finishes onboarding.
        is SessionState.SignedIn -> when {
            s.profile.role == "attorney" -> AttorneyApp(vm, s)
            s.profile.identityStatus == "approved" -> SignedInApp(vm, s)
            else -> OnboardingFlow(vm, s)
        }
    }
    if (showServer) {
        ServerSettingsDialog(
            current = serverUrl,
            onSave = { vm.setServerUrl(it); showServer = false },
            onDismiss = { showServer = false },
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SignedInApp(vm: SurpayViewModel, session: SessionState.SignedIn) {
    val nav = rememberNavController()
    val form by vm.form.collectAsStateWithLifecycle()
    val matches by vm.matches.collectAsStateWithLifecycle()
    val claims by vm.claims.collectAsStateWithLifecycle()
    val agreement by vm.agreement.collectAsStateWithLifecycle()
    val counties by vm.counties.collectAsStateWithLifecycle()
    val backStack by nav.currentBackStackEntryAsState()
    val route = backStack?.destination?.route
    // Onboarding (ID approved, at least one home) is done by the time we get here.
    val start = remember { if (session.profile.addresses.isEmpty()) Routes.SETUP else Routes.MATCHES }

    LaunchedEffect(Unit) {
        vm.refreshMatches()
        vm.refreshClaims()
    }
    LaunchedEffect(route) { vm.clearFormError() }

    /** After starting a claim, go straight to whatever the person has to do next. */
    fun continueClaim(claim: com.surpay.app.data.Claim) {
        nav.navigate(Routes.claim(claim.id)) { launchSingleTop = true }
        when (claim.nextAction) {
            "verify_identity" -> nav.navigate(Routes.identity(claim.id))
            "sign_agreement" -> nav.navigate(Routes.agreement(claim.id))
        }
    }

    Scaffold(
        topBar = {
            Column {
                TopAppBar(
                    title = {
                        Text(
                            when (route) {
                                Routes.SETUP -> "Set up your search"
                                Routes.PROFILE -> "Profile"
                                Routes.DETAIL -> "Surplus details"
                                Routes.CLAIMS -> "My claims"
                                Routes.CLAIM -> "Claim status"
                                Routes.IDENTITY -> "Identity check"
                                Routes.AGREEMENT -> "Agreement"
                                else -> "Your money"
                            },
                        )
                    },
                    navigationIcon = {
                        if (route != null && route !in Routes.TABS && route != Routes.SETUP) {
                            IconButton(onClick = { nav.popBackStack() }, modifier = Modifier.testTag("back")) {
                                Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                            }
                        }
                    },
                )
                if (session.offlineDemo) {
                    Surface(color = Color(0xFFFFF1D6), contentColor = Color(0xFF6B4A00), modifier = Modifier.fillMaxWidth()) {
                        Text(
                            "Offline demo: made-up data on this phone. No Surpay server is connected yet.",
                            Modifier.padding(horizontal = 16.dp, vertical = 8.dp).testTag("offlineBanner"),
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }
            }
        },
        bottomBar = {
            if (route in Routes.TABS) {
                NavigationBar {
                    NavigationBarItem(
                        selected = route == Routes.MATCHES,
                        onClick = { nav.switchTab(Routes.MATCHES) },
                        icon = { Icon(Icons.Filled.AttachMoney, contentDescription = null) },
                        label = { Text("My money") },
                    )
                    NavigationBarItem(
                        selected = route == Routes.CLAIMS,
                        onClick = { nav.switchTab(Routes.CLAIMS) },
                        icon = { Icon(Icons.Filled.Checklist, contentDescription = null) },
                        label = { Text("My claims") },
                        modifier = Modifier.testTag("claimsTab"),
                    )
                    NavigationBarItem(
                        selected = route == Routes.PROFILE,
                        onClick = { nav.switchTab(Routes.PROFILE) },
                        icon = { Icon(Icons.Filled.Person, contentDescription = null) },
                        label = { Text("Profile") },
                    )
                }
            }
        },
    ) { padding ->
        NavHost(navController = nav, startDestination = start, modifier = Modifier.padding(padding)) {
            composable(Routes.SETUP) {
                ProfileScreen(
                    profile = session.profile, form = form, firstRun = true,
                    onSave = { update ->
                        vm.saveProfile(update) {
                            nav.navigate(Routes.MATCHES) { popUpTo(Routes.SETUP) { inclusive = true } }
                        }
                    },
                    onLogout = vm::logout,
                    counties = counties, onStateChosen = vm::loadCounties,
                )
            }
            composable(Routes.MATCHES) {
                MatchesScreen(
                    state = matches,
                    onRefresh = vm::refreshMatches,
                    onOpen = { nav.navigate(Routes.detail(it.recordId)) },
                    onEditProfile = { nav.switchTab(Routes.PROFILE) },
                )
            }
            composable(Routes.CLAIMS) {
                LaunchedEffect(Unit) { vm.refreshClaims() }
                ClaimsScreen(
                    claims = claims,
                    onOpen = { nav.navigate(Routes.claim(it.id)) },
                    onFindMoney = { nav.switchTab(Routes.MATCHES) },
                )
            }
            composable(Routes.PROFILE) {
                ProfileScreen(
                    profile = session.profile, form = form, firstRun = false,
                    onSave = { update -> vm.saveProfile(update) { nav.switchTab(Routes.MATCHES) } },
                    onLogout = vm::logout,
                    counties = counties, onStateChosen = vm::loadCounties,
                )
            }
            composable(Routes.DETAIL, arguments = listOf(navArgument("id") { type = NavType.IntType })) { entry ->
                val id = entry.arguments?.getInt("id")
                val match = matches.data?.matches?.firstOrNull { it.recordId == id }
                if (match == null) {
                    LaunchedEffect(Unit) { nav.popBackStack() }
                } else {
                    MatchDetailScreen(
                        match = match,
                        claiming = form.busy,
                        error = form.error ?: matches.error,
                        onStartClaim = { vm.startClaim(match.recordId) { continueClaim(it) } },
                        onViewClaim = {
                            claims?.firstOrNull { it.recordId == match.recordId }?.let { nav.navigate(Routes.claim(it.id)) }
                                ?: vm.startClaim(match.recordId) { nav.navigate(Routes.claim(it.id)) }
                        },
                    )
                }
            }
            composable(Routes.CLAIM, arguments = listOf(navArgument("id") { type = NavType.IntType })) { entry ->
                val id = entry.arguments!!.getInt("id")
                LaunchedEffect(id) { vm.reloadClaim(id) }
                val claim = claims?.firstOrNull { it.id == id }
                if (claim == null) {
                    LoadingScreen("Loading your claim…")
                } else {
                    ClaimScreen(
                        claim = claim,
                        onVerifyIdentity = { nav.navigate(Routes.identity(id)) },
                        onSignAgreement = { nav.navigate(Routes.agreement(id)) },
                        onViewAgreement = { nav.navigate(Routes.agreement(id)) },
                    )
                }
            }
            composable(Routes.IDENTITY, arguments = listOf(navArgument("id") { type = NavType.IntType })) { entry ->
                val id = entry.arguments!!.getInt("id")
                IdentityScreen(
                    profile = session.profile, form = form,
                    onSubmit = { body ->
                        vm.submitIdentity(body) {
                            // Straight on to signing, then back to the claim's timeline.
                            nav.navigate(Routes.agreement(id)) { popUpTo(Routes.IDENTITY) { inclusive = true } }
                        }
                    },
                )
            }
            composable(Routes.AGREEMENT, arguments = listOf(navArgument("id") { type = NavType.IntType })) { entry ->
                val id = entry.arguments!!.getInt("id")
                LaunchedEffect(id) { vm.loadAgreement(id) }
                AgreementScreen(
                    agreement = agreement, expectedName = session.profile.fullName, form = form,
                    onSign = { name -> vm.signAgreement(id, name) { nav.popBackStack(Routes.CLAIM, inclusive = false) } },
                )
            }
        }
    }
}

private fun NavHostController.switchTab(route: String) = navigate(route) {
    popUpTo(graph.startDestinationId) { saveState = true }
    launchSingleTop = true
    restoreState = true
}

/**
 * Sign-up continues here until staff approve the ID: verify identity, list homes, then wait.
 * No results, tabs or claims are reachable from here, so an unverified account can't look anyone up.
 */
@Composable
private fun OnboardingFlow(vm: SurpayViewModel, session: SessionState.SignedIn) {
    val form by vm.form.collectAsStateWithLifecycle()
    val preview by vm.preview.collectAsStateWithLifecycle()
    val counties by vm.counties.collectAsStateWithLifecycle()
    var editingHomes by rememberSaveable { mutableStateOf(false) }
    val p = session.profile
    val stage = when {
        p.identityStatus == null || p.identityStatus == "rejected" -> "identity"
        p.addresses.isEmpty() || editingHomes -> "homes"
        else -> "waiting"
    }
    LaunchedEffect(stage) { vm.clearFormError() }

    Surface(Modifier.fillMaxSize()) {
        when (stage) {
            "identity" -> IdentityScreen(
                profile = p, form = form, onSubmit = { vm.submitIdentity(it) },
                modifier = Modifier.systemBarsPadding(),
                header = { OnboardingHeader(step = 1) },
            )
            "homes" -> ProfileScreen(
                profile = p, form = form, firstRun = !editingHomes,
                onSave = { update -> vm.saveProfile(update) { editingHomes = false } },
                onLogout = vm::logout,
                counties = counties, onStateChosen = vm::loadCounties,
                modifier = Modifier.systemBarsPadding(),
                header = { OnboardingHeader(step = 2) },
            )
            else -> VerifyingScreen(
                profile = p, preview = preview,
                onRefresh = { vm.refreshProfile(); vm.refreshPreview() },
                onEditHomes = { editingHomes = true },
                onLogout = vm::logout,
            )
        }
    }
}

/** Partner attorneys: apply, wait for license verification, then work their cases. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AttorneyApp(vm: SurpayViewModel, session: SessionState.SignedIn) {
    val state by vm.attorney.collectAsStateWithLifecycle()
    val form by vm.form.collectAsStateWithLifecycle()
    val counties by vm.counties.collectAsStateWithLifecycle()
    val terms by vm.terms.collectAsStateWithLifecycle()
    val cases by vm.cases.collectAsStateWithLifecycle()
    val documents by vm.documents.collectAsStateWithLifecycle()
    var openCase by rememberSaveable { mutableStateOf<Int?>(null) }
    LaunchedEffect(Unit) { vm.loadAttorney() }

    val profile = state.profile
    Surface(Modifier.fillMaxSize()) {
        when {
            !state.loaded -> LoadingScreen()
            state.error != null && profile == null -> UnreachableScreen(state.error!!, "", onRetry = vm::loadAttorney, onServerSettings = {})
            profile == null || profile.status == "rejected" -> AttorneyApplyScreen(
                name = session.profile.fullName, form = form, counties = counties, terms = terms,
                rejectedNote = profile?.reviewNote?.ifBlank { "Please re-apply." }.takeIf { profile?.status == "rejected" },
                onStateChosen = { vm.loadCounties(it); vm.loadTerms(it) },
                onSubmit = vm::applyAsAttorney, onLogout = vm::logout,
                modifier = Modifier.systemBarsPadding(),
            )
            profile.status == "pending" -> AttorneyPendingScreen(profile, onRefresh = vm::loadAttorney, onLogout = vm::logout)
            else -> {
                LaunchedEffect(Unit) { vm.loadCases() }
                val current = openCase?.let { id -> cases?.firstOrNull { it.id == id } }
                Scaffold(
                    topBar = {
                        TopAppBar(
                            title = { Text(if (current != null) "Case #${current.id}" else "Your cases") },
                            navigationIcon = {
                                if (current != null) {
                                    IconButton(onClick = { openCase = null }, modifier = Modifier.testTag("back")) {
                                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                                    }
                                }
                            },
                            actions = { if (current == null) TextButton(onClick = vm::logout) { Text("Sign out") } },
                        )
                    },
                ) { padding ->
                    if (current == null) {
                        CasesScreen(profile, cases, onOpen = { openCase = it.id; vm.reloadCase(it.id) }, onRefresh = vm::loadCases,
                            modifier = Modifier.padding(padding))
                    } else {
                        CaseDetailScreen(
                            case = current, form = form, documents = documents,
                            onAccept = { vm.acceptCase(current.id) },
                            onDecline = { reason -> vm.declineCase(current.id, reason) { openCase = null } },
                            onStatus = { s, note -> vm.updateCase(current.id, s, note) },
                            onLoadDocument = { kind -> vm.loadDocument(current.id, kind) },
                            modifier = Modifier.padding(padding),
                        )
                    }
                }
            }
        }
    }
}
