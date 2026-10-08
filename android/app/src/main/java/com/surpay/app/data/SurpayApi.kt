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
import retrofit2.http.Path
import retrofit2.http.Query
import java.util.concurrent.TimeUnit

// Mirrors backend/surpay/schemas.py. Money is always integer cents.

@Serializable
data class Address(
    val id: Int? = null,
    val street: String,
    val city: String = "",
    val state: String,
    val zip: String = "",
    val county: String = "",
)

@Serializable
data class SignupRequest(
    val email: String,
    val password: String,
    @SerialName("full_name") val fullName: String,
    val phone: String = "",
    /** claimant | attorney */
    val role: String = "claimant",
    @SerialName("accept_terms") val acceptTerms: Boolean = false,
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
    /** null (ID not submitted) | pending | approved | rejected. Results unlock at approved. */
    @SerialName("identity_status") val identityStatus: String? = null,
    @SerialName("identity_note") val identityNote: String = "",
    @SerialName("name_locked") val nameLocked: Boolean = false,
    /** claimant | attorney */
    val role: String = "claimant",
    /** False when the Terms or Privacy Notice changed since they accepted: ask again. */
    @SerialName("terms_current") val termsCurrent: Boolean = true,
    @SerialName("unread_notifications") val unreadNotifications: Int = 0,
    @SerialName("deletion_requested") val deletionRequested: Boolean = false,
)

@Serializable
data class MatchPreview(
    @SerialName("identity_status") val identityStatus: String? = null,
    @SerialName("possible_matches") val possibleMatches: Int = 0,
)

/** Which law gives the owner this money, what they must prove, and the deadline. */
@Serializable
data class Legal(
    val law: String = "",
    val right: String = "",
    val process: String = "",
    val deadline: String = "",
    /** What happens to the money if nobody claims it in time. */
    @SerialName("if_missed") val ifMissed: String = "",
    val proof: List<String> = emptyList(),
    /** Extra proof when claiming for a family member: heir | power_of_attorney | guardian -> items. */
    @SerialName("family_proof") val familyProof: Map<String, List<String>> = emptyMap(),
    val note: String = "",
    /** Surpay is a platform, not a law firm; the claimant and their attorney make the claim. */
    val facilitator: String = "",
    val constitutional: String = "",
    val sources: List<String> = emptyList(),
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
    val legal: Legal = Legal(),
    /** Approximate last day to claim. */
    @SerialName("deadline_date") val deadlineDate: String? = null,
    @SerialName("relative_id") val relativeId: Int? = null,
    /** Family claims: "Mary Parent (your parent, as heir)". */
    @SerialName("on_behalf_of") val onBehalfOf: String? = null,
)

@Serializable
data class MatchesResponse(
    val matches: List<Match>,
    @SerialName("total_amount_cents") val totalAmountCents: Long,
    @SerialName("total_estimated_net_cents") val totalEstimatedNetCents: Long,
    @SerialName("records_searched") val recordsSearched: Int,
    @SerialName("counties_covered") val countiesCovered: List<String>,
    val disclaimer: String = "",
)

@Serializable
data class ClaimRequest(@SerialName("record_id") val recordId: Int)

@Serializable
data class TimelineStep(
    val status: String,
    val title: String,
    val description: String,
    /** done | current | upcoming | stopped */
    val state: String,
    @SerialName("completed_at") val completedAt: String? = null,
    @SerialName("estimate_start") val estimateStart: String? = null,
    @SerialName("estimate_end") val estimateEnd: String? = null,
)

@Serializable
data class Claim(
    val id: Int,
    @SerialName("record_id") val recordId: Int,
    val status: String,
    val county: String,
    val state: String,
    val reference: String,
    @SerialName("amount_cents") val amountCents: Long,
    @SerialName("estimated_net_cents") val estimatedNetCents: Long = 0,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
    /** verify_identity | sign_agreement | null */
    @SerialName("next_action") val nextAction: String? = null,
    /** pending | approved | rejected | null (not submitted yet) */
    @SerialName("identity_status") val identityStatus: String? = null,
    @SerialName("identity_note") val identityNote: String = "",
    val timeline: List<TimelineStep> = emptyList(),
    @SerialName("estimated_completion_start") val estimatedCompletionStart: String? = null,
    @SerialName("estimated_completion_end") val estimatedCompletionEnd: String? = null,
    val disclaimer: String = "",
    val legal: Legal = Legal(),
    /** The partner attorney, once they've accepted the case. */
    val attorney: AttorneyPublic? = null,
    @SerialName("fee_pct") val feePct: Double = 0.0,
    @SerialName("deadline_date") val deadlineDate: String? = null,
    @SerialName("on_behalf_of") val onBehalfOf: String? = null,
    /** Messages with the attorney: open once they accept the case. */
    @SerialName("chat_open") val chatOpen: Boolean = false,
    @SerialName("unread_messages") val unreadMessages: Int = 0,
)

@Serializable
data class AttorneyPublic(val name: String, val firm: String = "", val phone: String = "", val bar: String = "")

@Serializable
data class AttorneyApplication(
    @SerialName("full_name") val fullName: String,
    @SerialName("bar_state") val barState: String,
    @SerialName("bar_number") val barNumber: String,
    val firm: String,
    val phone: String,
    @SerialName("office_address") val officeAddress: String,
    val counties: List<String>,
    @SerialName("bar_card_b64") val barCardB64: String,
    @SerialName("accept_terms") val acceptTerms: Boolean,
)

@Serializable
data class AttorneyProfile(
    @SerialName("full_name") val fullName: String,
    @SerialName("bar_state") val barState: String,
    @SerialName("bar_number") val barNumber: String,
    val firm: String = "",
    val phone: String = "",
    @SerialName("office_address") val officeAddress: String = "",
    val counties: List<String> = emptyList(),
    /** pending | approved | rejected */
    val status: String,
    @SerialName("review_note") val reviewNote: String = "",
    @SerialName("fee_per_case_cents") val feePerCaseCents: Long = 0,
    val terms: String = "",
)

@Serializable
data class AttorneyTerms(
    val version: String,
    val text: String,
    @SerialName("fee_per_case_cents") val feePerCaseCents: Long,
)

@Serializable
data class CaseRelative(
    val name: String,
    val relationship: String = "",
    val basis: String = "",
    @SerialName("date_of_death") val dateOfDeath: String? = null,
    val documents: List<String> = emptyList(),
)

@Serializable
data class CaseClaimant(
    val name: String,
    @SerialName("date_of_birth") val dateOfBirth: String? = null,
    @SerialName("current_address") val currentAddress: String = "",
    @SerialName("other_names") val otherNames: List<String> = emptyList(),
    @SerialName("ssn_last4") val ssnLast4: String = "",
    @SerialName("id_type") val idType: String = "",
    @SerialName("has_id_back") val hasIdBack: Boolean = false,
    val homes: List<String> = emptyList(),
    /** Set when the client claims as a family member's heir or under their authority. */
    val relative: CaseRelative? = null,
)

@Serializable
data class CaseAgreement(
    val text: String,
    @SerialName("signature_name") val signatureName: String,
    @SerialName("signed_at") val signedAt: String,
    @SerialName("fee_pct") val feePct: Double = 0.0,
    @SerialName("document_sha256") val documentSha256: String = "",
    @SerialName("ip_address") val ipAddress: String = "",
    val device: String = "",
    @SerialName("has_signature_image") val hasSignatureImage: Boolean = false,
)

/** How claims are filed in a state, step by step, and what must be printed. */
@Serializable
data class FilingGuide(
    val where: String = "",
    val online: String = "",
    val steps: List<String> = emptyList(),
    val print: List<String> = emptyList(),
)

@Serializable
data class CaseRecord(
    @SerialName("owner_name") val ownerName: String = "",
    @SerialName("owner_address") val ownerAddress: String = "",
)

@Serializable
data class CaseEvent(val status: String, val note: String = "", val at: String)

/** A case as the attorney sees it. claimant/agreement/record are filled in only after accepting. */
@Serializable
data class AttorneyCase(
    val id: Int,
    /** offered | accepted */
    @SerialName("assignment_status") val assignmentStatus: String,
    val status: String,
    val county: String,
    val state: String,
    val reference: String,
    @SerialName("sale_type") val saleType: String,
    @SerialName("sale_date") val saleDate: String? = null,
    @SerialName("amount_cents") val amountCents: Long,
    @SerialName("fee_cents") val feeCents: Long,
    /** "" | due | paid */
    @SerialName("payout_status") val payoutStatus: String = "",
    @SerialName("assigned_at") val assignedAt: String? = null,
    @SerialName("accepted_at") val acceptedAt: String? = null,
    @SerialName("source_url") val sourceUrl: String = "",
    val legal: Legal = Legal(),
    @SerialName("on_behalf_of") val onBehalfOf: String? = null,
    @SerialName("filing_guide") val filingGuide: FilingGuide = FilingGuide(),
    @SerialName("chat_open") val chatOpen: Boolean = false,
    @SerialName("unread_messages") val unreadMessages: Int = 0,
    val claimant: CaseClaimant? = null,
    val agreement: CaseAgreement? = null,
    val record: CaseRecord? = null,
    val history: List<CaseEvent> = emptyList(),
)

@Serializable
data class CaseStatusRequest(val status: String, val note: String = "")

@Serializable
data class DeclineRequest(val reason: String = "")

@Serializable
data class IdentityRequest(
    @SerialName("legal_name") val legalName: String,
    @SerialName("date_of_birth") val dateOfBirth: String,
    @SerialName("ssn_last4") val ssnLast4: String,
    val phone: String,
    val street: String,
    val city: String,
    val state: String,
    val zip: String,
    @SerialName("id_type") val idType: String,
    @SerialName("id_front_b64") val idFrontB64: String,
    @SerialName("id_back_b64") val idBackB64: String? = null,
    @SerialName("selfie_b64") val selfieB64: String,
    val consent: Boolean,
    @SerialName("other_names") val otherNames: List<String> = emptyList(),
)

@Serializable
data class AgreementDoc(
    val version: String,
    val text: String,
    @SerialName("fee_pct") val feePct: Double,
    val signed: Boolean,
    @SerialName("signature_name") val signatureName: String? = null,
    @SerialName("signed_at") val signedAt: String? = null,
    /** The typed signature must match this: the name on the verified ID. */
    @SerialName("expected_name") val expectedName: String = "",
    @SerialName("document_sha256") val documentSha256: String = "",
)

@Serializable
data class SignRequest(
    @SerialName("signature_name") val signatureName: String,
    val agreed: Boolean,
    /** The signature drawn on screen, as a base64 PNG. */
    @SerialName("signature_png_b64") val signaturePngB64: String,
)

@Serializable
data class Message(
    val id: Int,
    /** attorney | claimant */
    @SerialName("sender_role") val senderRole: String,
    val body: String,
    @SerialName("created_at") val createdAt: String,
    val read: Boolean = false,
)

@Serializable
data class Chat(
    val messages: List<Message> = emptyList(),
    @SerialName("can_send") val canSend: Boolean = false,
    @SerialName("waiting_reason") val waitingReason: String = "",
    val counterpart: String = "",
    @SerialName("code_of_conduct") val codeOfConduct: List<String> = emptyList(),
)

@Serializable
data class MessageRequest(val body: String)

@Serializable
data class AppNotification(
    val id: Int,
    /** claim_update | money_released | message | case_offer | identity | relative */
    val kind: String,
    val title: String,
    val body: String = "",
    @SerialName("claim_id") val claimId: Int? = null,
    @SerialName("created_at") val createdAt: String,
    val read: Boolean = false,
)

@Serializable
data class Notifications(val items: List<AppNotification> = emptyList(), val unread: Int = 0)

@Serializable
data class Policies(
    @SerialName("terms_version") val termsVersion: String,
    val terms: String,
    @SerialName("privacy_version") val privacyVersion: String,
    val privacy: String,
)

/** A family member whose surplus the user claims as heir, or under a power of attorney / guardianship. */
@Serializable
data class Relative(
    val id: Int,
    @SerialName("full_name") val fullName: String,
    @SerialName("other_names") val otherNames: List<String> = emptyList(),
    val relationship: String,
    val basis: String,
    @SerialName("date_of_death") val dateOfDeath: String? = null,
    /** pending | approved | rejected */
    @SerialName("review_status") val reviewStatus: String,
    @SerialName("review_note") val reviewNote: String = "",
    val addresses: List<Address> = emptyList(),
    @SerialName("submitted_at") val submittedAt: String = "",
)

@Serializable
data class RelativeRequest(
    @SerialName("full_name") val fullName: String,
    @SerialName("other_names") val otherNames: List<String> = emptyList(),
    val relationship: String,
    val basis: String,
    @SerialName("date_of_death") val dateOfDeath: String? = null,
    @SerialName("death_certificate_b64") val deathCertificateB64: String? = null,
    @SerialName("relationship_proof_b64") val relationshipProofB64: String,
    @SerialName("authority_document_b64") val authorityDocumentB64: String? = null,
    val addresses: List<Address>,
    val consent: Boolean,
)

@Serializable
data class DeleteResult(val deleted: Boolean, val message: String)

@Serializable
data class Coverage(
    val records: Int,
    @SerialName("total_amount_cents") val totalAmountCents: Long,
    val counties: List<String>,
    @SerialName("demo_login") val demoLogin: Boolean = false,
)

/** Identifies this install and phone in the audit trail. Android doesn't let apps read the IMEI. */
data class DeviceInfo(
    val deviceId: String = "",
    val installId: String = "",
    val model: String = "",
    val osVersion: String = "",
    val appVersion: String = "",
) {
    fun headers() = mapOf(
        "X-Device-Id" to deviceId, "X-Install-Id" to installId, "X-Device-Model" to model,
        "X-OS-Version" to osVersion, "X-App-Version" to appVersion,
    )
}

@Serializable
data class ApiError(val detail: kotlinx.serialization.json.JsonElement? = null)

interface SurpayApi {
    @GET("coverage") suspend fun coverage(): Coverage
    @POST("auth/signup") suspend fun signup(@Body body: SignupRequest): TokenResponse
    @POST("auth/login") suspend fun login(@Body body: LoginRequest): TokenResponse
    @POST("auth/demo") suspend fun demoLogin(): TokenResponse
    @GET("me") suspend fun me(): Profile
    @PUT("me") suspend fun updateMe(@Body body: ProfileUpdate): Profile
    @GET("me/matches") suspend fun matches(): MatchesResponse
    @GET("me/matches/preview") suspend fun matchesPreview(): MatchPreview
    @POST("me/claims") suspend fun startClaim(@Body body: ClaimRequest): Claim
    @GET("me/claims") suspend fun claims(): List<Claim>
    @GET("me/claims/{id}") suspend fun claim(@Path("id") id: Int): Claim
    @POST("me/identity") suspend fun submitIdentity(@Body body: IdentityRequest): List<Claim>
    @GET("me/claims/{id}/agreement") suspend fun agreement(@Path("id") id: Int): AgreementDoc
    @POST("me/claims/{id}/agreement") suspend fun signAgreement(@Path("id") id: Int, @Body body: SignRequest): Claim
    @GET("counties") suspend fun counties(@Query("state") state: String): List<String>
    @POST("me/claims/{id}/withdraw") suspend fun withdrawClaim(@Path("id") id: Int): Claim
    @GET("me/claims/{id}/messages") suspend fun messages(@Path("id") id: Int): Chat
    @POST("me/claims/{id}/messages") suspend fun sendMessage(@Path("id") id: Int, @Body body: MessageRequest): Chat

    // --- Notifications, family members, privacy ---
    @GET("me/notifications") suspend fun notifications(@Query("after_id") afterId: Int = 0): Notifications
    @POST("me/notifications/read") suspend fun markNotificationsRead(): kotlinx.serialization.json.JsonObject
    @GET("policies") suspend fun policies(): Policies
    @POST("me/consents/accept-current") suspend fun acceptCurrentTerms(): kotlinx.serialization.json.JsonObject
    @GET("me/relatives") suspend fun relatives(): List<Relative>
    @POST("me/relatives") suspend fun addRelative(@Body body: RelativeRequest): Relative
    @retrofit2.http.DELETE("me/relatives/{id}") suspend fun removeRelative(@Path("id") id: Int): kotlinx.serialization.json.JsonObject
    @GET("me/export") suspend fun exportData(): okhttp3.ResponseBody
    @POST("me/delete") suspend fun deleteAccount(): DeleteResult
    @POST("auth/logout-all") suspend fun logoutEverywhere(): kotlinx.serialization.json.JsonObject

    // --- Partner attorneys ---
    @GET("attorney/terms") suspend fun attorneyTerms(@Query("state") state: String): AttorneyTerms
    @POST("attorney/apply") suspend fun attorneyApply(@Body body: AttorneyApplication): AttorneyProfile
    /** 404 = not applied yet. */
    @GET("attorney/me") suspend fun attorneyMe(): AttorneyProfile
    @GET("attorney/cases") suspend fun attorneyCases(): List<AttorneyCase>
    @GET("attorney/cases/{id}") suspend fun attorneyCase(@Path("id") id: Int): AttorneyCase
    @POST("attorney/cases/{id}/accept") suspend fun acceptCase(@Path("id") id: Int): AttorneyCase
    @POST("attorney/cases/{id}/decline") suspend fun declineCase(@Path("id") id: Int, @Body body: DeclineRequest): kotlinx.serialization.json.JsonObject
    @POST("attorney/cases/{id}/status") suspend fun updateCase(@Path("id") id: Int, @Body body: CaseStatusRequest): AttorneyCase
    @GET("attorney/cases/{id}/documents/{kind}") suspend fun caseDocument(@Path("id") id: Int, @Path("kind") kind: String): okhttp3.ResponseBody
    @GET("attorney/cases/{id}/packet") suspend fun casePacket(@Path("id") id: Int): okhttp3.ResponseBody
    @GET("attorney/cases/{id}/messages") suspend fun caseMessages(@Path("id") id: Int): Chat
    @POST("attorney/cases/{id}/messages") suspend fun sendCaseMessage(@Path("id") id: Int, @Body body: MessageRequest): Chat

    companion object {
        val json = Json { ignoreUnknownKeys = true; explicitNulls = false }

        /** Retrofit needs a fixed base URL; the real server is swapped in per request. */
        private const val PLACEHOLDER_BASE = "http://surpay.invalid/"

        /**
         * [baseUrlProvider] is read on every request, so changing the server in Settings takes
         * effect immediately. Timeouts are long because a free Render instance can take about a
         * minute to wake up.
         */
        fun create(
            baseUrlProvider: () -> String,
            tokenProvider: () -> String?,
            device: DeviceInfo = DeviceInfo(),
        ): SurpayApi {
            val rewrite = Interceptor { chain ->
                val original = chain.request()
                val base = baseUrlProvider().let { if (it.endsWith("/")) it else "$it/" }.toHttpUrl()
                val url = base.newBuilder()
                    .addEncodedPathSegments(original.url.encodedPath.removePrefix("/"))
                    .encodedQuery(original.url.encodedQuery)
                    .build()
                val builder = original.newBuilder().url(url)
                tokenProvider()?.let { builder.header("Authorization", "Bearer $it") }
                // Recorded in the server's audit trail with each action (who did what, from which phone).
                device.headers().forEach { (k, v) -> if (v.isNotBlank()) builder.header(k, v) }
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
