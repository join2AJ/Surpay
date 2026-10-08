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

/** Tick, type the name, sign. Leaves the app on the claim's timeline. */
@OptIn(ExperimentalTestApi::class)
fun ComposeContentTestRule.signAgreement(name: String, timeout: Long = 15_000) {
    waitUntilAtLeastOneExists(hasTestTag("agreementText"), timeout)
    onNodeWithTag("agree").performScrollTo().performClick()
    onNodeWithTag("signature").performScrollTo().performTextInput(name)
    onNodeWithTag("sign").performScrollTo().performClick()
}
