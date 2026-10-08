package com.surpay.app.data

import retrofit2.converter.kotlinx.serialization.asConverterFactory
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import java.util.concurrent.TimeUnit

// Mirrors backend/surpay/schemas.py. Money is always integer cents.

@Serializable
data class Address(
    val id: Int? = null,
    val street: String,
    val city: String = "",
    val state: String,
    val zip: String = "",
)

@Serializable
data class SignupRequest(
    val email: String,
    val password: String,
    @SerialName("full_name") val fullName: String,
    val phone: String = "",
)

@Serializable
data class LoginRequest(val email: String, val password: String)

@Serializable
data class Profile(
    val id: Int,
    val email: String,
    @SerialName("full_name") val fullName: String,
    @SerialName("other_names") val otherNames: List<String> = emptyList(),
    val phone: String = "",
    val addresses: List<Address> = emptyList(),
)

@Serializable
data class ProfileUpdate(
    @SerialName("full_name") val fullName: String,
    @SerialName("other_names") val otherNames: List<String>,
    val phone: String,
    val addresses: List<Address>,
)

@Serializable
data class TokenResponse(val token: String, val user: Profile)

@Serializable
data class Match(
    @SerialName("record_id") val recordId: Int,
    val confidence: String,
    @SerialName("address_matched") val addressMatched: Boolean,
    val state: String,
    val county: String,
    @SerialName("sale_type") val saleType: String,
    val reference: String,
    @SerialName("owner_name") val ownerName: String,
    @SerialName("owner_address") val ownerAddress: String,
    @SerialName("amount_cents") val amountCents: Long,
    @SerialName("fee_pct") val feePct: Double,
    @SerialName("estimated_fee_cents") val estimatedFeeCents: Long,
    @SerialName("estimated_net_cents") val estimatedNetCents: Long,
    @SerialName("sale_date") val saleDate: String? = null,
    @SerialName("source_url") val sourceUrl: String = "",
    @SerialName("last_seen") val lastSeen: String,
    @SerialName("claim_status") val claimStatus: String? = null,
)

@Serializable
data class MatchesResponse(
    val matches: List<Match>,
    @SerialName("total_amount_cents") val totalAmountCents: Long,
    @SerialName("total_estimated_net_cents") val totalEstimatedNetCents: Long,
    @SerialName("records_searched") val recordsSearched: Int,
    @SerialName("counties_covered") val countiesCovered: List<String>,
)

@Serializable
data class ClaimRequest(@SerialName("record_id") val recordId: Int)

@Serializable
data class Claim(
    val id: Int,
    @SerialName("record_id") val recordId: Int,
    val status: String,
    val county: String,
    val state: String,
    val reference: String,
    @SerialName("amount_cents") val amountCents: Long,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
)

@Serializable
data class Coverage(
    val records: Int,
    @SerialName("total_amount_cents") val totalAmountCents: Long,
    val counties: List<String>,
)

@Serializable
data class ApiError(val detail: kotlinx.serialization.json.JsonElement? = null)

interface SurpayApi {
    @GET("coverage") suspend fun coverage(): Coverage
    @POST("auth/signup") suspend fun signup(@Body body: SignupRequest): TokenResponse
    @POST("auth/login") suspend fun login(@Body body: LoginRequest): TokenResponse
    @GET("me") suspend fun me(): Profile
    @PUT("me") suspend fun updateMe(@Body body: ProfileUpdate): Profile
    @GET("me/matches") suspend fun matches(): MatchesResponse
    @POST("me/claims") suspend fun startClaim(@Body body: ClaimRequest): Claim
    @GET("me/claims") suspend fun claims(): List<Claim>

    companion object {
        val json = Json { ignoreUnknownKeys = true; explicitNulls = false }

        /** Retrofit needs a fixed base URL; the real server is swapped in per request. */
        private const val PLACEHOLDER_BASE = "http://surpay.invalid/"

        /**
         * [baseUrlProvider] is read on every request, so changing the server in Settings takes
         * effect immediately. Timeouts are long because a free Render instance can take about a
         * minute to wake up.
         */
        fun create(baseUrlProvider: () -> String, tokenProvider: () -> String?): SurpayApi {
            val rewrite = Interceptor { chain ->
                val original = chain.request()
                val base = baseUrlProvider().let { if (it.endsWith("/")) it else "$it/" }.toHttpUrl()
                val url = base.newBuilder()
                    .addEncodedPathSegments(original.url.encodedPath.removePrefix("/"))
                    .encodedQuery(original.url.encodedQuery)
                    .build()
                val builder = original.newBuilder().url(url)
                tokenProvider()?.let { builder.header("Authorization", "Bearer $it") }
                chain.proceed(builder.build())
            }
            val client = OkHttpClient.Builder()
                .addInterceptor(rewrite)
                .connectTimeout(30, TimeUnit.SECONDS)
                .readTimeout(90, TimeUnit.SECONDS)
                .callTimeout(120, TimeUnit.SECONDS)
                .build()
            return Retrofit.Builder()
                .baseUrl(PLACEHOLDER_BASE)
                .client(client)
                .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
                .build()
                .create(SurpayApi::class.java)
        }
    }
}
