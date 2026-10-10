package com.surpay.app

import androidx.activity.ComponentActivity
import androidx.compose.material3.Surface
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import com.surpay.app.data.ServerStore
import com.surpay.app.data.SurpayApi
import com.surpay.app.data.SurpayRepository
import com.surpay.app.data.TokenStore
import com.surpay.app.ui.SurpayApp
import com.surpay.app.ui.SurpayViewModel
import com.surpay.app.ui.theme.SurpayTheme
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config

/** "Admin" on the welcome screen opens the staff dashboard in the browser with a demo-only pass. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
@OptIn(ExperimentalTestApi::class)
class AdminDemoTest {
    @get:Rule val compose = createAndroidComposeRule<ComponentActivity>()

    @Test fun adminDemoOpensTheDashboard() {
        val url = System.getProperty("surpay.e2eUrl")
        assumeTrue("set -Pe2eUrl to run", !url.isNullOrBlank())
        val tokens = TokenStore(compose.activity).also { runBlocking { it.clear() } }
        val server = ServerStore(compose.activity, url!!)
        val vm = SurpayViewModel(SurpayRepository(SurpayApi.create({ server.current }, { tokens.cached }), tokens), server)
        compose.setContent { SurpayTheme { Surface { SurpayApp(vm) } } }

        compose.waitUntilAtLeastOneExists(hasTestTag("demoAdmin"), 15_000)
        compose.onNodeWithTag("demoAdmin").performScrollTo().performClick()
        compose.waitUntil(15_000) { shadowOf(compose.activity).peekNextStartedActivity() != null }
        val opened = shadowOf(compose.activity).nextStartedActivity.data.toString()
        assertTrue(opened, opened.startsWith("${url}admin#demo="))

        compose.onNodeWithTag("staffDashboard").performScrollTo().performClick()
        compose.waitUntil(5_000) { shadowOf(compose.activity).peekNextStartedActivity() != null }
        assertTrue(shadowOf(compose.activity).nextStartedActivity.data.toString() == "${url}admin")
    }
}
