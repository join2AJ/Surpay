package com.surpay.app

import androidx.compose.material3.Surface
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.assert
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.test.performTextClearance
import androidx.test.core.app.ApplicationProvider
import com.github.takahirom.roborazzi.captureRoboImage
import com.surpay.app.data.ServerStore
import com.surpay.app.data.SurpayApi
import com.surpay.app.data.SurpayRepository
import com.surpay.app.data.TokenStore
import com.surpay.app.ui.LocalPhotoSource
import com.surpay.app.ui.SurpayApp
import com.surpay.app.ui.SurpayViewModel
import com.surpay.app.ui.theme.SurpayTheme
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.junit.Assert.assertEquals
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** A new attorney applies in the app, gets approved, receives a verified client's case, accepts and files it. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w411dp-h891dp-xxhdpi")
@OptIn(ExperimentalTestApi::class)
class AttorneyEndToEndTest {
    @get:Rule val compose = createComposeRule()
    private val http = OkHttpClient()
    private val timeout = 15_000L

    private fun call(url: String, method: String = "GET", body: String? = null, headers: Map<String, String> = emptyMap()): JsonElement {
        val b = Request.Builder().url(url)
        headers.forEach { (k, v) -> b.header(k, v) }
        if (method == "POST") b.post((body ?: "{}").toRequestBody("application/json".toMediaType()))
        return http.newCall(b.build()).execute().use { r ->
            check(r.isSuccessful) { "$method $url -> ${r.code} ${r.body?.string()}" }
            Json.parseToJsonElement(r.body!!.string())
        }
    }

    private fun shot(name: String) = compose.onRoot().captureRoboImage("build/outputs/roborazzi/attorney_$name.png")

    @Test fun attorneyEnrollsAndWorksACase() {
        val url = System.getProperty("surpay.e2eUrl")
        val adminToken = System.getProperty("surpay.e2eAdminToken")
        assumeTrue("set -Pe2eUrl and -Pe2eAdminToken to run", !url.isNullOrBlank() && !adminToken.isNullOrBlank())
        val admin = mapOf("X-Admin-Token" to adminToken!!)

        // Earlier test runs leave approved attorneys behind: retire them so this one gets the case.
        (call("${url}admin/attorneys?review_status=approved", headers = admin) as JsonArray).forEach {
            val id = it.jsonObject["user_id"]!!.jsonPrimitive.int
            call("${url}admin/attorneys/$id", "POST", """{"decision":"rejected","note":"test cleanup"}""", admin)
        }

        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val tokens = TokenStore(context).also { runBlocking { it.clear() } }
        val server = ServerStore(context, url!!)
        val vm = SurpayViewModel(SurpayRepository(SurpayApi.create({ server.current }, { tokens.cached }), tokens), server)
        compose.setContent {
            CompositionLocalProvider(LocalPhotoSource provides fakeCamera) { SurpayTheme { Surface { SurpayApp(vm) } } }
        }

        // 1. Attorney account: "I'm an attorney" on the welcome screen
        compose.waitUntilAtLeastOneExists(hasTestTag("roleAttorney"), timeout)
        compose.createAccount("attorney", "Alex Counsel", "alex+${System.currentTimeMillis()}@law.example")

        // 2. Application: license, counties, bar card, terms
        compose.waitUntilAtLeastOneExists(hasTestTag("barNumber"), timeout)
        compose.onNodeWithTag("barState").performScrollTo().performClick()
        compose.onNodeWithText("OH").performScrollTo().performClick()
        compose.onNodeWithTag("barNumber").performTextInput("0099123")
        compose.onNodeWithTag("firm").performScrollTo().performTextInput("Counsel LLC")
        compose.onNodeWithTag("attyPhone").performScrollTo().performTextInput("6145550100")
        compose.onNodeWithTag("office").performScrollTo().performTextInput("1 Court St, Springfield, OH 45501")
        compose.waitUntilAtLeastOneExists(hasTestTag("countyFilter"), timeout)
        compose.onNodeWithTag("countyFilter").performScrollTo().performTextInput("Demo")
        compose.onNodeWithTag("county_Demo County").performClick()
        compose.onNodeWithText("1 selected").assertExists()
        compose.onNodeWithTag("barCardCamera").performScrollTo().performClick()
        compose.waitUntilAtLeastOneExists(hasTestTag("feePerCase"), timeout)
        compose.onNodeWithTag("acceptTerms").performScrollTo().performClick()
        shot("1_apply")
        compose.onNodeWithTag("submitApplication").performScrollTo().performClick()

        // 3. Waiting for license verification; staff approve
        compose.waitUntilAtLeastOneExists(hasTestTag("attyPending"), timeout)
        shot("2_pending")
        val attorneyId = call("${url}me", headers = mapOf("Authorization" to "Bearer ${tokens.cached}")).jsonObject["id"]!!.jsonPrimitive.int
        call("${url}admin/attorneys/$attorneyId", "POST", """{"decision":"approved"}""", admin)

        // 4. A verified client (the demo person) signs a claim in Demo County: it's offered to this attorney
        val demo = call("${url}auth/demo", "POST").jsonObject["token"]!!.jsonPrimitive.content
        val claimant = mapOf("Authorization" to "Bearer $demo")
        val recordId = call("${url}me/matches", headers = claimant).jsonObject["matches"]!!.jsonArray[0].jsonObject["record_id"]!!.jsonPrimitive.int
        val claimId = call("${url}me/claims", "POST", """{"record_id":$recordId}""", claimant).jsonObject["id"]!!.jsonPrimitive.int
        call("${url}me/claims/$claimId/agreement", "POST",
            """{"signature_name":"Jordan Testwell","agreed":true,"signature_png_b64":"$SIGNATURE_PNG_B64"}""", claimant)

        compose.onNodeWithText("Check status now").performClick()
        compose.waitUntilAtLeastOneExists(hasTestTag("case$claimId"), timeout)
        compose.onNodeWithTag("case$claimId").assertExists()
        shot("3_cases")

        // 5. Offer shows no personal details; accepting reveals the client and documents
        compose.onNodeWithTag("case$claimId").performClick()
        compose.waitUntilAtLeastOneExists(hasTestTag("acceptCase"), timeout)
        compose.onNodeWithText("Jordan Testwell", substring = true).assertDoesNotExist()
        compose.onNodeWithTag("conflictChecked").performScrollTo().performClick()
        compose.onNodeWithTag("acceptCase").performScrollTo().performClick()
        compose.waitUntilAtLeastOneExists(hasTestTag("client"), timeout)
        compose.onNode(hasTestTag("client")).assert(androidx.compose.ui.test.hasAnyDescendant(hasText("Jordan Testwell")))
        compose.onNodeWithTag("filingGuide").performScrollTo().assertExists()
        shot("4_case")
        assertEquals("\"attorney_assigned\"", call("${url}me/claims/$claimId", headers = claimant).jsonObject["status"].toString())

        // 6. The attorney writes first; contact details are blocked; the client can then reply
        compose.onNodeWithTag("caseChat").performScrollTo().performClick()
        compose.waitUntilAtLeastOneExists(hasTestTag("chatInput"), timeout)
        compose.onNodeWithTag("chatInput").performTextInput("Call me at 614-555-0100")
        compose.onNodeWithTag("chatWarning").assertExists()
        compose.onNodeWithTag("chatInput").performTextClearance()
        compose.onNodeWithTag("chatInput").performTextInput("Hello Jordan, I'm handling your claim. I'll file this week.")
        compose.onNodeWithTag("chatSend").performClick()
        compose.waitUntilAtLeastOneExists(hasText("Hello Jordan", substring = true), timeout)
        shot("4b_chat")
        call("${url}me/claims/$claimId/messages", "POST", """{"body":"Thank you!"}""", claimant)
        compose.onNodeWithTag("back").performClick()
        compose.waitUntilAtLeastOneExists(hasTestTag("status_filed"), timeout)

        // 7. Mark filed; the client's timeline shows it and names the attorney
        compose.onNodeWithTag("status_filed").performScrollTo().performClick()
        compose.onNodeWithTag("dialogNote").performScrollTo().performTextInput("Filed with Demo County, case 2026-CV-123")
        compose.onNodeWithTag("dialogConfirm").performScrollTo().performClick()
        compose.waitUntilAtLeastOneExists(hasTestTag("status_approved"), timeout)
        shot("5_filed")
        val mine = call("${url}me/claims/$claimId", headers = claimant).jsonObject
        assertEquals("\"filed\"", mine["status"].toString())
        assertEquals("\"Alex Counsel\"", mine["attorney"]!!.jsonObject["name"].toString())

        // 8. Waiting for the court, approved, money released: the client is notified at each step
        for (s in listOf("hearing_pending", "approved", "paid")) {
            compose.waitUntil(timeout) {
                compose.onAllNodes(hasTestTag("status_$s") and androidx.compose.ui.test.isEnabled()).fetchSemanticsNodes().isNotEmpty()
            }
            compose.onNodeWithTag("status_$s").performScrollTo().performClick()
            compose.waitUntilAtLeastOneExists(hasTestTag("dialogConfirm"), timeout)
            compose.onNodeWithTag("dialogConfirm").performScrollTo().performClick()
        }
        compose.waitUntilAtLeastOneExists(hasText("Case closed", substring = true), timeout)
        val kinds = call("${url}me/notifications", headers = claimant).jsonObject["items"]!!.jsonArray
            .map { it.jsonObject["kind"]!!.jsonPrimitive.content }
        assertEquals("money_released", kinds.first())
    }
}
