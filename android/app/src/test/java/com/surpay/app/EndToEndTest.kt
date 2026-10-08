package com.surpay.app

import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.hasText
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
import androidx.compose.material3.Surface
import androidx.compose.runtime.CompositionLocalProvider
import com.surpay.app.ui.LocalPhotoSource
import kotlinx.coroutines.runBlocking
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/**
 * Drives the real app against a real backend seeded with `python -m surpay.cli seed-demo`.
 * Skipped unless -Pe2eUrl=... is passed to Gradle.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w411dp-h891dp-xxhdpi")
@OptIn(ExperimentalTestApi::class)
class EndToEndTest {
    @get:Rule val compose = createComposeRule()

    private fun shot(name: String) = compose.onRoot().captureRoboImage("build/outputs/roborazzi/e2e_$name.png")

    @Test fun signUpFindMoneyAndStartClaim() {
        val url = System.getProperty("surpay.e2eUrl")
        assumeTrue("set -Pe2eUrl to run", !url.isNullOrBlank())

        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val tokens = TokenStore(context).also { runBlocking { it.clear() } } // start signed out
        val server = ServerStore(context, url!!)
        val vm = SurpayViewModel(SurpayRepository(SurpayApi.create({ server.current }, { tokens.cached }), tokens), server)
        compose.setContent {
            CompositionLocalProvider(LocalPhotoSource provides fakeCamera) { SurpayTheme { Surface { SurpayApp(vm) } } }
        }
        val timeout = 15_000L

        // Sign up
        compose.waitUntilAtLeastOneExists(hasText("Create your free account"), timeout)
        compose.waitUntilAtLeastOneExists(hasText("Tracking", substring = true), timeout)
        compose.onNodeWithTag("name").performTextInput("Jordan Testwell")
        compose.onNodeWithTag("email").performTextInput("jordan+${System.currentTimeMillis()}@example.com")
        compose.onNodeWithTag("password").performTextInput("correct horse battery")
        shot("1_signup")
        compose.onNodeWithTag("submit").performScrollTo().performClick()

        // First-run setup: add a previous address
        compose.waitUntilAtLeastOneExists(hasText("Where have you owned property?"), timeout)
        compose.onNodeWithTag("street0").performTextInput("412 Maple Ridge Road")
        compose.onNodeWithTag("city0").performTextInput("Springfield")
        compose.onNodeWithTag("state0").performScrollTo().performClick()
        compose.onNodeWithText("OH").performScrollTo().performClick()
        compose.onNodeWithTag("zip0").performScrollTo().performTextInput("45501")
        // County list comes from the server's registry of every US county.
        compose.waitUntilAtLeastOneExists(hasText("Type to search 88 counties in OH"), timeout)
        compose.onNodeWithTag("county0").performScrollTo().performTextInput("Clark")
        compose.onNodeWithText("Clark County").performClick()
        shot("2_setup")
        compose.onNodeWithTag("saveProfile").performScrollTo().performClick()

        // Matches: both Testwell records, the address-confirmed one first
        compose.waitUntilAtLeastOneExists(hasTestTag("totalAmount"), timeout)
        compose.onNodeWithTag("totalAmount").assertExists()
        compose.onNodeWithText("$34,575.50").assertExists() // 28,450.00 + 6,125.50
        compose.onNodeWithText("Name & address match").assertExists()
        shot("3_matches")

        // Detail + start claim
        compose.onNodeWithText("$28,450.00").performClick()
        compose.waitUntilAtLeastOneExists(hasTestTag("startClaim"), timeout)
        compose.onNodeWithText("Estimated to you").assertExists()
        compose.onNodeWithText("$24,182.50").assertExists() // after 15% fee
        shot("4_detail")
        compose.onNodeWithTag("startClaim").performScrollTo().performClick()

        // Identity check opens straight away, then the agreement, then the timeline.
        compose.waitUntilAtLeastOneExists(hasTestTag("dob"), timeout)
        shot("5_identity")
        compose.completeIdentity()
        compose.waitUntilAtLeastOneExists(hasTestTag("agreementText"), timeout)
        compose.onNodeWithText("Fee: 15%", substring = true).assertExists()
        shot("6_agreement")
        compose.signAgreement("Jordan Testwell")
        compose.waitUntilAtLeastOneExists(hasTestTag("eta"), timeout)
        compose.onNodeWithText("Agreement signed: ID under review").assertExists()
        compose.onNodeWithTag("disclaimer").performScrollTo().assertExists()
        compose.onNodeWithTag("eta").performScrollTo()
        shot("7_timeline")

        // The claim is listed under My claims for checking later.
        compose.onNodeWithTag("back").performClick()
        compose.waitUntilAtLeastOneExists(hasTestTag("viewClaim"), timeout)
        compose.onNodeWithTag("back").performClick()
        compose.onNodeWithTag("claimsTab").performClick()
        compose.waitUntilAtLeastOneExists(hasText("Agreement signed: ID under review"), timeout)
        shot("8_my_claims")
    }

    @Test fun demoAccountOneTap() {
        val url = System.getProperty("surpay.e2eUrl")
        assumeTrue("set -Pe2eUrl to run", !url.isNullOrBlank())

        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val tokens = TokenStore(context).also { runBlocking { it.clear() } } // start signed out
        val server = ServerStore(context, url!!)
        val vm = SurpayViewModel(SurpayRepository(SurpayApi.create({ server.current }, { tokens.cached }), tokens), server)
        compose.setContent { SurpayTheme { Surface { SurpayApp(vm) } } }

        compose.waitUntilAtLeastOneExists(hasTestTag("demoLogin"), 15_000)
        shot("6_demo_button")
        compose.onNodeWithTag("demoLogin").performClick()
        // Straight to matches: the demo profile already has an address, so the strong match shows.
        compose.waitUntilAtLeastOneExists(hasTestTag("totalAmount"), 15_000)
        compose.onNodeWithText("$34,575.50").assertExists()
        compose.onNodeWithText("Name & address match").assertExists()
        shot("7_demo_matches")
    }
}
