package com.surpay.app.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
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
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
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
import com.surpay.app.ui.screens.AuthScreen
import com.surpay.app.ui.screens.LoadingScreen
import com.surpay.app.ui.screens.ServerSettingsDialog
import com.surpay.app.ui.screens.UnreachableScreen
import com.surpay.app.ui.screens.MatchDetailScreen
import com.surpay.app.ui.screens.MatchesScreen
import com.surpay.app.ui.screens.ProfileScreen

private object Routes {
    const val SETUP = "setup"
    const val MATCHES = "matches"
    const val PROFILE = "profile"
    const val DETAIL = "match/{id}"
    fun detail(id: Int) = "match/$id"
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
        is SessionState.SignedIn -> SignedInApp(vm, s)
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
    val backStack by nav.currentBackStackEntryAsState()
    val route = backStack?.destination?.route

    LaunchedEffect(Unit) { vm.refreshMatches() }

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
                                else -> "Your money"
                            },
                        )
                    },
                    navigationIcon = {
                        if (route == Routes.DETAIL) {
                            IconButton(onClick = { nav.popBackStack() }) {
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
            if (route == Routes.MATCHES || route == Routes.PROFILE) {
                NavigationBar {
                    NavigationBarItem(
                        selected = route == Routes.MATCHES,
                        onClick = { nav.switchTab(Routes.MATCHES) },
                        icon = { Icon(Icons.Filled.AttachMoney, contentDescription = null) },
                        label = { Text("My money") },
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
        NavHost(
            navController = nav,
            startDestination = if (session.isNewUser) Routes.SETUP else Routes.MATCHES,
            modifier = Modifier.padding(padding),
        ) {
            composable(Routes.SETUP) {
                ProfileScreen(
                    profile = session.profile, form = form, firstRun = true,
                    onSave = { update ->
                        vm.saveProfile(update) {
                            nav.navigate(Routes.MATCHES) { popUpTo(Routes.SETUP) { inclusive = true } }
                        }
                    },
                    onLogout = vm::logout,
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
            composable(Routes.PROFILE) {
                ProfileScreen(
                    profile = session.profile, form = form, firstRun = false,
                    onSave = { update -> vm.saveProfile(update) { nav.switchTab(Routes.MATCHES) } },
                    onLogout = vm::logout,
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
                        claiming = matches.claimingRecordId == match.recordId,
                        error = matches.error,
                        onStartClaim = { vm.startClaim(match.recordId) },
                    )
                }
            }
        }
    }
}

private fun NavHostController.switchTab(route: String) = navigate(route) {
    popUpTo(graph.startDestinationId) { saveState = true }
    launchSingleTop = true
    restoreState = true
}
