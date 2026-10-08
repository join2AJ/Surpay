package com.surpay.app

import androidx.compose.material3.Surface
import androidx.compose.runtime.CompositionLocalProvider
import com.surpay.app.ui.LocalPhotoSource
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import androidx.test.core.app.ApplicationProvider
import com.github.takahirom.roborazzi.captureRoboImage
import com.surpay.app.data.ServerStore
import com.surpay.app.data.SurpayApi
import com.surpay.app.data.SurpayRepository
import com.surpay.app.data.TokenStore
import com.surpay.app.ui.SurpayApp
import com.surpay.app.ui.SurpayViewModel
import com.surpay.app.ui.theme.SurpayTheme
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/**
 * The backend isn't deployed yet: every request gets the 404 Render returns for an unknown
 * service. The demo button must still work, on the phone alone, and say so.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w411dp-h891dp-xxhdpi")
@OptIn(ExperimentalTestApi::class)
class OfflineDemoTest {
    @get:Rule val compose = createComposeRule()
    private val server = MockWebServer().apply {
        dispatcher = object : okhttp3.mockwebserver.Dispatcher() {
            override fun dispatch(request: okhttp3.mockwebserver.RecordedRequest) =
                MockResponse().setResponseCode(404).setHeader("x-render-routing", "no-server").setBody("Not Found")
        }
        start()
    }

    @After fun tearDown() = server.shutdown()

    private fun launch() {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val tokens = TokenStore(context).also { runBlocking { it.clear() } }
        val store = ServerStore(context, server.url("/").toString())
        val vm = SurpayViewModel(SurpayRepository(SurpayApi.create({ store.current }, { tokens.cached }), tokens), store)
        compose.setContent {
            CompositionLocalProvider(LocalPhotoSource provides fakeCamera) { SurpayTheme { Surface { SurpayApp(vm) } } }
        }
    }

    private fun shot(name: String) = compose.onRoot().captureRoboImage("build/outputs/roborazzi/offline_$name.png")

    @Test fun demoButtonWorksWithoutAServer() {
        launch()
        compose.waitUntilAtLeastOneExists(hasTestTag("demoLogin"), 10_000)
        compose.onNodeWithTag("demoLogin").performClick()

        compose.waitUntilAtLeastOneExists(hasTestTag("totalAmount"), 10_000)
        compose.onNodeWithTag("offlineBanner").assertExists()
        compose.onNodeWithText("$34,575.50").assertExists()
        compose.onNodeWithText("Name & address match").assertExists()
        compose.onNodeWithText("$29,389.18", substring = true).assertExists() // same net as the server
        shot("1_matches")

        compose.onNodeWithText("$28,450.00").performClick()
        compose.waitUntilAtLeastOneExists(hasTestTag("startClaim"), 10_000)
        compose.onNodeWithTag("startClaim").performScrollTo().performClick()
        compose.completeIdentity()
        compose.signAgreement("Jordan Testwell")
        compose.waitUntilAtLeastOneExists(hasTestTag("eta"), 10_000)
        compose.onNodeWithText("Agreement signed: ID under review").assertExists()
    }

    @Test fun signUpExplainsThereIsNoServer() {
        launch()
        compose.waitUntilAtLeastOneExists(hasTestTag("name"), 10_000)
        compose.onNodeWithTag("name").performTextInput("Real Person")
        compose.onNodeWithTag("email").performTextInput("real@example.com")
        compose.onNodeWithTag("password").performTextInput("correct horse battery")
        compose.onNodeWithTag("submit").performScrollTo().performClick()
        compose.waitUntilAtLeastOneExists(hasTestTag("error"), 10_000)
        compose.onNodeWithText("No Surpay server found at this address", substring = true).assertExists()
        shot("2_no_server_error")
    }
}
