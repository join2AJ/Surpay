package com.surpay.app

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.ComposeContentTestRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.test.performTouchInput
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.test.swipe
import com.surpay.app.ui.PhotoSource
import java.io.ByteArrayOutputStream

/** Stands in for the camera: every photo is a small real JPEG. */
val fakeCamera = PhotoSource { _, onResult ->
    val bmp = Bitmap.createBitmap(320, 200, Bitmap.Config.ARGB_8888)
    Canvas(bmp).drawColor(Color.rgb(30, 110, 80))
    onResult(ByteArrayOutputStream().also { bmp.compress(Bitmap.CompressFormat.JPEG, 80, it) }.toByteArray())
}

/** Fill in the identity screen, add photos, submit. Leaves the app on the agreement screen. */
@OptIn(ExperimentalTestApi::class)
fun ComposeContentTestRule.completeIdentity(timeout: Long = 15_000) {
    waitUntilAtLeastOneExists(hasTestTag("dob"), timeout)
    onNodeWithTag("dob").performScrollTo().performTextInput("04021980")
    onNodeWithTag("ssn4").performScrollTo().performTextInput("1234")
    onNodeWithTag("phone").performScrollTo().performTextInput("5550100000")
    onNodeWithTag("curStreet").performScrollTo().performTextInput("9 New Home Ln")
    onNodeWithTag("curCity").performScrollTo().performTextInput("Columbus")
    onNodeWithTag("curState").performScrollTo().performClick()
    onNodeWithText("OH").performScrollTo().performClick()
    onNodeWithTag("curZip").performScrollTo().performTextInput("43004")
    onNodeWithTag("idFrontCamera").performScrollTo().performClick()
    onNodeWithTag("selfieCamera").performScrollTo().performClick()
    waitUntilAtLeastOneExists(hasText("Added ✓"), timeout)
    onNodeWithTag("consent").performScrollTo().performClick()
    onNodeWithTag("submitIdentity").performScrollTo().performClick()
}

/** Type the name, draw a signature, tick, sign. Leaves the app on the claim's timeline. */
@OptIn(ExperimentalTestApi::class)
fun ComposeContentTestRule.signAgreement(name: String, timeout: Long = 15_000) {
    waitUntilAtLeastOneExists(hasTestTag("agreementText"), timeout)
    onNodeWithTag("signature").performScrollTo().performTextInput(name)
    onNodeWithText("Matches your verified ID").assertExists()
    onNodeWithTag("signaturePad").performScrollTo().performTouchInput {
        swipe(Offset(width * 0.15f, height * 0.6f), Offset(width * 0.45f, height * 0.3f), 200)
        swipe(Offset(width * 0.45f, height * 0.3f), Offset(width * 0.8f, height * 0.65f), 200)
    }
    onNodeWithTag("agree").performScrollTo().performClick()
    onNodeWithTag("sign").performScrollTo().assertIsEnabled().performClick()
}

/** Welcome screen: pick "Find money owed to me" (or attorney), fill the form, accept the terms, submit. */
fun ComposeContentTestRule.createAccount(role: String, name: String, email: String) {
    onNodeWithTag(if (role == "attorney") "roleAttorney" else "roleClaimant").performScrollTo().performClick()
    onNodeWithTag("name").performTextInput(name)
    onNodeWithTag("email").performTextInput(email)
    onNodeWithTag("password").performTextInput("correct horse battery")
    onNodeWithTag("agreeTerms").performScrollTo().performClick()
    onNodeWithTag("submit").performScrollTo().performClick()
}

/** A small real PNG, standing in for a signature drawn on screen. */
val SIGNATURE_PNG_B64: String by lazy {
    val bmp = Bitmap.createBitmap(300, 120, Bitmap.Config.ARGB_8888)
    Canvas(bmp).drawColor(Color.WHITE)
    java.util.Base64.getEncoder().encodeToString(ByteArrayOutputStream().also { bmp.compress(Bitmap.CompressFormat.PNG, 100, it) }.toByteArray())
}

/** A small real JPEG as base64, for API calls that upload a photo. */
val JPEG_B64: String by lazy {
    val bmp = Bitmap.createBitmap(120, 80, Bitmap.Config.ARGB_8888)
    Canvas(bmp).drawColor(Color.rgb(200, 200, 190))
    java.util.Base64.getEncoder().encodeToString(ByteArrayOutputStream().also { bmp.compress(Bitmap.CompressFormat.JPEG, 85, it) }.toByteArray())
}
