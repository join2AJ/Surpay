package com.surpay.app

import com.surpay.app.data.SurpayApi
import com.surpay.app.data.userMessage
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test

/** Payloads below are copied from real backend responses. */
class ApiContractTest {
    private val server = MockWebServer()
    private var token: String? = "abc"
    private lateinit var api: SurpayApi

    @Before fun setUp() {
        server.start()
        api = SurpayApi.create(server.url("/").toString()) { token }
    }

    @After fun tearDown() = server.shutdown()

    @Test fun parsesMatchesAndSendsToken() = runTest {
        server.enqueue(MockResponse().setBody(
            """{"matches":[{"record_id":1,"confidence":"strong","address_matched":true,"state":"OH",
            "county":"Demo","sale_type":"tax_sale","reference":"Case D-1001","owner_name":"Jordan Testwell",
            "owner_address":"412 Maple Ridge Rd","amount_cents":2845000,"fee_pct":15.0,
            "estimated_fee_cents":426750,"estimated_net_cents":2418250,"sale_date":"2024-06-17",
            "source_url":"","last_seen":"2026-10-08T10:32:00Z","claim_status":null,"new_field":1}],
            "total_amount_cents":2845000,"total_estimated_net_cents":2418250,"records_searched":5,
            "counties_covered":["Demo County, OH"]}""",
        ))
        val r = api.matches()
        assertEquals(2845000L, r.matches[0].amountCents)
        assertNull(r.matches[0].claimStatus)
        assertEquals("Bearer abc", server.takeRequest().getHeader("Authorization"))
    }

    @Test fun omitsAuthHeaderWhenSignedOut() = runTest {
        token = null
        server.enqueue(MockResponse().setBody("""{"records":0,"total_amount_cents":0,"counties":[]}"""))
        api.coverage()
        assertNull(server.takeRequest().getHeader("Authorization"))
    }

    @Test fun errorMessagesComeFromServerDetail() = runTest {
        server.enqueue(MockResponse().setResponseCode(409).setBody("""{"detail":"An account with this email already exists"}"""))
        val e = runCatching { api.coverage() }.exceptionOrNull()!!
        assertEquals("An account with this email already exists", e.userMessage())

        server.enqueue(MockResponse().setResponseCode(422).setBody(
            """{"detail":[{"type":"string_too_short","loc":["body","password"],"msg":"String should have at least 8 characters"}]}""",
        ))
        val v = runCatching { api.coverage() }.exceptionOrNull()!!
        assertEquals("String should have at least 8 characters", v.userMessage())

        server.enqueue(MockResponse().setResponseCode(500).setBody("oops"))
        assertEquals("Something went wrong (error 500). Please try again.", runCatching { api.coverage() }.exceptionOrNull()!!.userMessage())
    }
}
