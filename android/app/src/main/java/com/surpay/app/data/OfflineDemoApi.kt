package com.surpay.app.data

import java.time.Instant

/**
 * A stand-in for the server, used only by the demo button when no Surpay server is reachable
 * (e.g. the backend isn't deployed yet). Mirrors backend/surpay/demo.py: the same fictional
 * "Demo County" people and amounts, so the app can be tried end to end on a phone alone.
 */
class OfflineDemoApi : SurpayApi {
    private data class DemoRecord(
        val id: Int, val ref: String, val owner: String, val address: String,
        val street: String, val cents: Long, val sold: String,
    )

    private val records = listOf(
        DemoRecord(9001, "Case D-1001", "Jordan Testwell", "412 Maple Ridge Rd, Springfield, OH 45501", "412 maple ridge", 2_845_000, "2024-06-17"),
        DemoRecord(9002, "Case D-1002", "TESTWELL, JORDAN A", "88 Harbor View Dr, Springfield, OH 45502", "88 harbor view", 612_550, "2023-11-06"),
        DemoRecord(9003, "Case D-1003", "Casey Placeholder", "19 Elm St, Springfield, OH 45503", "19 elm", 1_210_000, "2024-02-12"),
        DemoRecord(9004, "Case D-1004", "Morgan & Riley Example", "7 Birch Ct, Springfield, OH 45504", "7 birch", 4_390_075, "2024-09-09"),
        DemoRecord(9005, "Case D-1005", "Avery Sampleton", "230 Lake Shore Blvd, Springfield, OH 45505", "230 lake shore", 98_013, "2025-01-21"),
    )
    private val feePct = 15.0
    private val now = Instant.now().toString()

    private var profile = freshProfile()
    /** recordId -> (status -> when reached), in step order. */
    private val claims = linkedMapOf<Int, LinkedHashMap<String, Instant>>()
    private val signed = mutableMapOf<Int, String>()
    private var identitySubmitted = false

    private fun freshProfile() = Profile(
        id = 0, email = "demo@surpay.test", fullName = DEMO_NAME,
        addresses = listOf(
            Address(id = 1, street = "412 Maple Ridge Rd", city = "Springfield", state = "OH", zip = "45501", county = "Clark County"),
        ),
    )

    /** Start over, like the server does on every demo sign-in. */
    fun reset() {
        profile = freshProfile()
        claims.clear()
        signed.clear()
        identitySubmitted = false
    }

    private fun nameMatches(owner: String): Boolean {
        val tokens = owner.lowercase().split(Regex("[^a-z]+")).filter { it.isNotEmpty() }.toSet()
        return (listOf(profile.fullName) + profile.otherNames).any { name ->
            val parts = name.lowercase().split(Regex("[^a-z]+")).filter { it.isNotEmpty() }
            parts.size >= 2 && parts.first() in tokens && parts.last() in tokens
        }
    }

    private fun addressMatches(r: DemoRecord): Boolean = profile.addresses.any {
        it.state.equals("OH", ignoreCase = true) &&
            it.street.lowercase().replace(Regex("\\s+"), " ").startsWith(r.street)
    }

    override suspend fun coverage() = Coverage(
        records = records.size,
        totalAmountCents = records.sumOf { it.cents },
        counties = listOf("Demo County, OH"),
        demoLogin = true,
    )

    override suspend fun demoLogin(): TokenResponse {
        reset()
        return TokenResponse(OFFLINE_DEMO_TOKEN, profile)
    }

    override suspend fun me() = profile

    override suspend fun updateMe(body: ProfileUpdate): Profile {
        profile = profile.copy(
            fullName = body.fullName, otherNames = body.otherNames, phone = body.phone,
            addresses = body.addresses.mapIndexed { i, a -> a.copy(id = i + 1) },
        )
        return profile
    }

    override suspend fun matches(): MatchesResponse {
        val matches = records.filter { nameMatches(it.owner) }.map { r ->
            // Same rounding as the server (Python round(): halves go to the even number).
            val fee = java.math.BigDecimal(r.cents * feePct / 100).setScale(0, java.math.RoundingMode.HALF_EVEN).toLong()
            Match(
                recordId = r.id, confidence = if (addressMatches(r)) "strong" else "likely",
                addressMatched = addressMatches(r), state = "OH", county = "Demo", saleType = "tax_sale",
                reference = r.ref, ownerName = r.owner, ownerAddress = r.address, amountCents = r.cents,
                feePct = feePct, estimatedFeeCents = fee, estimatedNetCents = r.cents - fee,
                saleDate = r.sold, sourceUrl = "", lastSeen = now, claimStatus = claims[r.id]?.keys?.last(),
            )
        }.sortedWith(compareBy<Match> { if (it.confidence == "strong") 0 else 1 }.thenByDescending { it.amountCents })
        return MatchesResponse(
            matches = matches,
            totalAmountCents = matches.sumOf { it.amountCents },
            totalEstimatedNetCents = matches.sumOf { it.estimatedNetCents },
            recordsSearched = records.size,
            countiesCovered = listOf("Demo County, OH"),
        )
    }

    private fun reach(recordId: Int, status: String) {
        claims.getValue(recordId).putIfAbsent(status, Instant.now())
    }

    private fun toClaim(recordId: Int): Claim {
        val r = records.first { it.id == recordId }
        val reached = claims.getValue(recordId)
        val status = reached.keys.last()
        val fee = java.math.BigDecimal(r.cents * feePct / 100).setScale(0, java.math.RoundingMode.HALF_EVEN).toLong()
        val timeline = demoTimeline(reached)
        val last = timeline.lastOrNull { it.estimateEnd != null }
        return Claim(
            id = recordId, recordId = recordId, status = status, county = "Demo", state = "OH",
            reference = r.ref, amountCents = r.cents, estimatedNetCents = r.cents - fee,
            createdAt = reached.values.first().toString(), updatedAt = reached.values.last().toString(),
            nextAction = when (status) {
                "requested" -> "verify_identity"
                "identity_submitted" -> "sign_agreement"
                else -> null
            },
            identityStatus = if (identitySubmitted) "pending" else null,
            timeline = timeline,
            estimatedCompletionStart = last?.estimateStart, estimatedCompletionEnd = last?.estimateEnd,
            disclaimer = DISCLAIMER,
        )
    }

    override suspend fun startClaim(body: ClaimRequest): Claim {
        val r = records.first { it.id == body.recordId }
        if (r.id !in claims) {
            claims[r.id] = linkedMapOf("requested" to Instant.now())
            if (identitySubmitted) reach(r.id, "identity_submitted")
        }
        return toClaim(r.id)
    }

    override suspend fun claims(): List<Claim> = claims.keys.reversed().map { toClaim(it) }

    override suspend fun claim(id: Int): Claim = toClaim(id)

    override suspend fun submitIdentity(body: IdentityRequest): List<Claim> {
        identitySubmitted = true
        claims.keys.forEach { reach(it, "identity_submitted") }
        return claims()
    }

    override suspend fun agreement(id: Int): AgreementDoc {
        val r = records.first { it.id == id }
        return AgreementDoc(
            version = "offline-demo",
            text = "SURPLUS FUNDS RECOVERY — CONTINGENCY FEE AGREEMENT (offline demo)\n\n" +
                "Claimant: ${profile.fullName}\nFunds: ${r.ref}, Demo County, OH\n\n" +
                "This is a demonstration only. On a real server this screen shows the full agreement: " +
                "${feePct.toInt()}% fee only if funds are recovered, nothing upfront, your right to claim the " +
                "funds yourself for free, and a 3-business-day cancellation window.",
            feePct = feePct, signed = id in signed, signatureName = signed[id],
        )
    }

    override suspend fun signAgreement(id: Int, body: SignRequest): Claim {
        signed[id] = body.signatureName
        reach(id, "agreement_signed")
        return toClaim(id)
    }

    override suspend fun counties(state: String): List<String> =
        if (state.equals("OH", ignoreCase = true)) listOf("Adams County", "Clark County", "Franklin County") else emptyList()

    override suspend fun signup(body: SignupRequest): TokenResponse = offline()
    override suspend fun login(body: LoginRequest): TokenResponse = offline()

    private fun offline(): Nothing =
        throw IllegalStateException("You're in the offline demo. Sign out to create a real account.")

    companion object {
        const val OFFLINE_DEMO_TOKEN = "offline-demo"
        const val DISCLAIMER = "All amounts and dates are approximate estimates, not a promise or guarantee."

        // Same steps and typical durations as backend/surpay/claims.py.
        private val STEPS = listOf(
            Triple("requested", "Claim started", 0 to 0),
            Triple("identity_submitted", "Identity submitted", 0 to 0),
            Triple("agreement_signed", "Agreement signed", 0 to 0),
            Triple("identity_verified", "Identity verified", 1 to 3),
            Triple("filed", "Claim filed", 7 to 21),
            Triple("approved", "Approved by the county or court", 30 to 120),
            Triple("paid", "Money released", 14 to 42),
        )

        fun demoTimeline(reached: Map<String, Instant>): List<TimelineStep> {
            val today = java.time.LocalDate.now()
            var lo = today
            var hi = today
            val currentIndex = STEPS.indexOfFirst { it.first !in reached }
            return STEPS.mapIndexed { i, (status, title, days) ->
                val at = reached[status]
                if (at != null) {
                    TimelineStep(status, title, "", "done", completedAt = at.toString())
                } else {
                    lo = maxOf(lo.plusDays(days.first.toLong()), today)
                    hi = maxOf(hi.plusDays(days.second.toLong()), lo)
                    TimelineStep(
                        status, title, "", if (i == currentIndex) "current" else "upcoming",
                        estimateStart = lo.toString(), estimateEnd = hi.toString(),
                    )
                }
            }
        }
        const val DEMO_NAME = "Jordan Testwell"
    }
}
