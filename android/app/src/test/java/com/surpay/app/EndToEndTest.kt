package com.surpay.app

import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.assertTextEquals
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithTag
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
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
        assumeTrue("set -Pe2eUrl and -Pe2eAdminToken to run",
            !url.isNullOrBlank() && !System.getProperty("surpay.e2eAdminToken").isNullOrBlank())

        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val tokens = TokenStore(context).also { runBlocking { it.clear() } } // start signed out
        val server = ServerStore(context, url!!)
        val vm = SurpayViewModel(SurpayRepository(SurpayApi.create({ server.current }, { tokens.cached }), tokens), server)
        compose.setContent {
            CompositionLocalProvider(LocalPhotoSource provides fakeCamera) { SurpayTheme { Surface { SurpayApp(vm) } } }
        }
        val timeout = 15_000L

        // Welcome: choose "Find money owed to me", create the account, accept the terms
        compose.waitUntilAtLeastOneExists(hasTestTag("roleClaimant"), timeout)
        compose.waitUntilAtLeastOneExists(hasText("Tracking", substring = true), timeout)
        shot("0_welcome")
        compose.createAccount("claimant", "Jordan Testwell", "jordan+${System.currentTimeMillis()}@example.com")
        shot("1_signup")

        // Step 2: verify identity before anything else
        compose.waitUntilAtLeastOneExists(hasText("Step 2 of 4 · Verify ID"), timeout)
        shot("2_identity")
        compose.completeIdentity()

        // Step 3: every home they've owned, with county
        compose.waitUntilAtLeastOneExists(hasText("Step 3 of 4 · Your homes"), timeout)
        compose.onNodeWithTag("street0").performTextInput("412 Maple Ridge Road")
        compose.onNodeWithTag("city0").performTextInput("Springfield")
        compose.onNodeWithTag("state0").performScrollTo().performClick()
        compose.onNodeWithText("OH").performScrollTo().performClick()
        compose.onNodeWithTag("zip0").performScrollTo().performTextInput("45501")
        compose.waitUntilAtLeastOneExists(hasText("counties in OH", substring = true), timeout)
        compose.onNodeWithTag("county0").performScrollTo().performTextInput("Clark")
        compose.onNodeWithText("Clark County").performClick()
        shot("3_homes")
        compose.onNodeWithTag("saveProfile").performScrollTo().performClick()

        // Step 4: waiting for review. A count only, no amounts.
        compose.waitUntilAtLeastOneExists(hasTestTag("verifyingTitle"), timeout)
        compose.waitUntilAtLeastOneExists(hasText("We found 2 possible records under your name"), timeout)
        compose.onAllNodes(hasText("$", substring = true)).assertCountEquals(0)
        shot("4_verifying")

        // Staff approve the ID on the review page; the app picks it up
        approveLatestIdentity(url, System.getProperty("surpay.e2eAdminToken")!!, tokens.cached!!)
        compose.onNodeWithText("Check status now").performScrollTo().performClick()

        // Results unlock
        compose.waitUntilAtLeastOneExists(hasTestTag("totalAmount"), timeout)
        compose.onNodeWithText("$34,575.50").assertExists()
        compose.onNodeWithText("Name & address match").assertExists()
        shot("5_matches")

        // Detail shows the law and what to prove; start claim goes straight to signing
        compose.onNodeWithText("$28,450.00").performClick()
        compose.waitUntilAtLeastOneExists(hasTestTag("legalCard"), timeout)
        compose.onNodeWithTag("legalLaw", useUnmergedTree = true).assertTextEquals("Ohio Revised Code § 5721.20")
        compose.onNodeWithTag("legalCard").performScrollTo().performClick()
        compose.onNodeWithText("An IRS Form W-9", substring = true).performScrollTo().assertExists()
        shot("6_legal")
        compose.onNodeWithTag("startClaim").performScrollTo().performClick()
        compose.waitUntilAtLeastOneExists(hasTestTag("agreementText"), timeout)
        compose.onNodeWithText("Fee: 17.5%", substring = true).assertExists()
        shot("6b_agreement")
        compose.signAgreement("Jordan Testwell")
        compose.waitUntilAtLeastOneExists(hasTestTag("eta"), timeout)
        compose.onNodeWithText("Identity verified: finding your attorney").assertExists()
        compose.onNodeWithTag("eta").performScrollTo()
        shot("7_timeline")

        // Listed under My claims to check any time
        compose.onNodeWithTag("back").performClick()
        compose.waitUntilAtLeastOneExists(hasTestTag("viewClaim"), timeout)
        compose.onNodeWithTag("back").performClick()
        compose.onNodeWithTag("claimsTab").performClick()
        compose.waitUntilAtLeastOneExists(hasText("Identity verified: finding your attorney"), timeout)
        shot("8_my_claims")

        // Account tab: family members, notifications, privacy
        compose.onNodeWithTag("accountTab").performClick()
        compose.waitUntilAtLeastOneExists(hasTestTag("navPrivacy"), timeout)
        shot("9_account")
        compose.onNodeWithTag("navPrivacy").performClick()
        compose.waitUntilAtLeastOneExists(hasTestTag("exportData"), timeout)
        shot("10_privacy")
    }

    /** What staff do on /admin: approve the newest pending ID. */
    private fun approveLatestIdentity(baseUrl: String, adminToken: String, userToken: String) {
        val http = okhttp3.OkHttpClient()
        val me = http.newCall(okhttp3.Request.Builder().url("${baseUrl}me").header("Authorization", "Bearer $userToken").build())
            .execute().use { it.body!!.string() }
        val id = Regex("\"id\":(\\d+)").find(me)!!.groupValues[1]
        val body = """{"decision":"approved"}""".toRequestBody("application/json".toMediaType())
        http.newCall(okhttp3.Request.Builder().url("${baseUrl}admin/users/$id/identity").header("X-Admin-Token", adminToken).post(body).build())
            .execute().use { check(it.isSuccessful) { "approve failed: ${it.code}" } }
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
        compose.onNodeWithTag("demoLogin").performScrollTo()
        shot("6_demo_button")
        compose.onNodeWithTag("demoLogin").performClick()
        // Straight to matches: the demo profile already has an address, so the strong match shows.
        compose.waitUntilAtLeastOneExists(hasTestTag("totalAmount"), 15_000)
        compose.onNodeWithText("$34,575.50").assertExists()
        compose.onNodeWithText("Name & address match").assertExists()
        shot("7_demo_matches")
    }

    @Test fun attorneyDemoOneTap() {
        val url = System.getProperty("surpay.e2eUrl")
        assumeTrue("set -Pe2eUrl to run", !url.isNullOrBlank())

        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val tokens = TokenStore(context).also { runBlocking { it.clear() } }
        val server = ServerStore(context, url!!)
        val vm = SurpayViewModel(SurpayRepository(SurpayApi.create({ server.current }, { tokens.cached }), tokens), server)
        compose.setContent { SurpayTheme { Surface { SurpayApp(vm) } } }

        compose.waitUntilAtLeastOneExists(hasTestTag("demoAttorneyLogin"), 15_000)
        compose.onNodeWithTag("demoAttorneyLogin").performScrollTo().performClick()
        // Straight to the case list, with a verified demo client's case waiting
        compose.waitUntilAtLeastOneExists(hasText("New cases: accept or decline"), 15_000)
        compose.onNodeWithText("Demo County, OH", substring = true).assertExists()
        shot("11_attorney_demo")
    }
}
