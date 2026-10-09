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
    /** Mirrors backend/surpay/fees.py defaults: average of 15% and the amount band, to the nearest 0.5%. */
    private fun feePct(cents: Long): Double {
        val band = when {
            cents <= 1_000_000 -> 25.0
            cents <= 5_000_000 -> 20.0
            cents <= 10_000_000 -> 15.0
            else -> 12.0
        }
        return Math.round((15.0 + band) / 2 * 2) / 2.0
    }
    private val now = Instant.now().toString()

    private var profile = freshProfile()
    /** recordId -> (status -> when reached), in step order. */
    private val claims = linkedMapOf<Int, LinkedHashMap<String, Instant>>()
    private val signed = mutableMapOf<Int, String>()
    private var identitySubmitted = true  // the demo person is pre-verified

    private fun freshProfile() = Profile(
        id = 0, email = "demo@surpay.test", fullName = DEMO_NAME,
        identityStatus = "approved", nameLocked = true,
        addresses = listOf(
            Address(id = 1, street = "412 Maple Ridge Rd", city = "Springfield", state = "OH", zip = "45501", county = "Clark County"),
        ),
    )

    /** Start over, like the server does on every demo sign-in. */
    fun reset() {
        profile = freshProfile()
        claims.clear()
        signed.clear()
        identitySubmitted = true
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
            val feePct = feePct(r.cents)
            val fee = java.math.BigDecimal(r.cents * feePct / 100).setScale(0, java.math.RoundingMode.HALF_EVEN).toLong()
            Match(
                recordId = r.id, confidence = if (addressMatches(r)) "strong" else "likely",
                addressMatched = addressMatches(r), state = "OH", county = "Demo", saleType = "tax_sale",
                reference = r.ref, ownerName = r.owner, ownerAddress = r.address, amountCents = r.cents,
                feePct = feePct, estimatedFeeCents = fee, estimatedNetCents = r.cents - fee,
                saleDate = r.sold, sourceUrl = "", lastSeen = now, claimStatus = claims[r.id]?.keys?.last(),
                legal = OHIO_LEGAL, deadlineDate = java.time.LocalDate.parse(r.sold).plusYears(3).toString(),
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
        val feePct = feePct(r.cents)
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
            identityStatus = if (identitySubmitted) "approved" else null,
            timeline = timeline,
            estimatedCompletionStart = last?.estimateStart, estimatedCompletionEnd = last?.estimateEnd,
            disclaimer = DISCLAIMER,
            legal = OHIO_LEGAL,
            feePct = feePct,
            deadlineDate = java.time.LocalDate.parse(r.sold).plusYears(3).toString(),
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

    override suspend fun matchesPreview() = MatchPreview("approved", records.count { nameMatches(it.owner) })

    override suspend fun claim(id: Int): Claim = toClaim(id)

    override suspend fun submitIdentity(body: IdentityRequest): List<Claim> {
        identitySubmitted = true
        claims.keys.forEach { reach(it, "identity_submitted") }
        return claims()
    }

    override suspend fun agreement(id: Int): AgreementDoc {
        val r = records.first { it.id == id }
        val pct = feePct(r.cents)
        return AgreementDoc(
            version = "offline-demo",
            text = "SURPLUS FUNDS RECOVERY AGREEMENT (offline demo)\n\n" +
                "Claimant: ${profile.fullName}\nFunds: ${r.ref}, Demo County, OH\n\n" +
                "This is a demonstration only. On a real server this screen shows the full agreement: " +
                "a ${pct}% fee only if funds are recovered, nothing upfront, your right to claim the " +
                "funds yourself for free, Surpay's role as a facilitator, and a 3-business-day cancellation window.",
            feePct = pct, signed = id in signed, signatureName = signed[id], expectedName = profile.fullName,
        )
    }

    override suspend fun signAgreement(id: Int, body: SignRequest): Claim {
        if (!body.signatureName.trim().equals(profile.fullName, ignoreCase = true)) {
            throw IllegalStateException("Type your full legal name exactly as it appears on your ID: ${profile.fullName}")
        }
        signed[id] = body.signatureName
        reach(id, "agreement_signed")
        reach(id, "identity_verified")  // ID already approved
        return toClaim(id)
    }

    override suspend fun counties(state: String): List<String> =
        if (state.equals("OH", ignoreCase = true)) listOf("Adams County", "Clark County", "Franklin County") else emptyList()

    override suspend fun messages(id: Int) = Chat(
        canSend = false, waitingReason = "Messages open once an attorney accepts your case.",
        counterpart = "Your attorney",
    )
    override suspend fun sendMessage(id: Int, body: MessageRequest): Chat = offline()
    override suspend fun notifications(afterId: Int) = Notifications()
    override suspend fun markNotificationsRead() = kotlinx.serialization.json.JsonObject(emptyMap())
    override suspend fun policies(): Policies = offline()
    override suspend fun acceptCurrentTerms() = kotlinx.serialization.json.JsonObject(emptyMap())
    override suspend fun relatives(): List<Relative> = emptyList()
    override suspend fun addRelative(body: RelativeRequest): Relative = offline()
    override suspend fun removeRelative(id: Int): kotlinx.serialization.json.JsonObject = offline()
    override suspend fun exportData(): okhttp3.ResponseBody = offline()
    override suspend fun deleteAccount(): DeleteResult = offline()
    override suspend fun logoutEverywhere() = kotlinx.serialization.json.JsonObject(emptyMap())
    override suspend fun casePacket(id: Int): okhttp3.ResponseBody = offline()
    override suspend fun caseMessages(id: Int): Chat = offline()
    override suspend fun sendCaseMessage(id: Int, body: MessageRequest): Chat = offline()

    override suspend fun attorneyTerms(state: String): AttorneyTerms = offline()
    override suspend fun attorneyApply(body: AttorneyApplication): AttorneyProfile = offline()
    override suspend fun attorneyMe(): AttorneyProfile = offline()
    override suspend fun attorneyCases(): List<AttorneyCase> = offline()
    override suspend fun attorneyCase(id: Int): AttorneyCase = offline()
    override suspend fun acceptCase(id: Int, body: AcceptRequest): AttorneyCase = offline()
    override suspend fun changeAttorney(id: Int): Claim = offline()
    override suspend fun changePassword(body: PasswordChange): TokenResponse = offline()
    override suspend fun declineCase(id: Int, body: DeclineRequest): kotlinx.serialization.json.JsonObject = offline()
    override suspend fun updateCase(id: Int, body: CaseStatusRequest): AttorneyCase = offline()
    override suspend fun caseDocument(id: Int, kind: String): okhttp3.ResponseBody = offline()

    override suspend fun demoAttorneyLogin(): TokenResponse = offline()
    override suspend fun signup(body: SignupRequest): TokenResponse = offline()
    override suspend fun login(body: LoginRequest): TokenResponse = offline()

    private fun offline(): Nothing =
        throw IllegalStateException("You're in the offline demo. Sign out to create a real account.")

    companion object {
        const val OFFLINE_DEMO_TOKEN = "offline-demo"
        const val DISCLAIMER = "All amounts and dates are approximate estimates, not a promise or guarantee."

        // Mirrors backend/surpay/legal.py for Ohio (the demo records are in Ohio).
        val OHIO_LEGAL = Legal(
            law = "Ohio Revised Code § 5721.20",
            right = "Money left after a tax foreclosure sale pays the taxes, costs and liens belongs to the former owner. " +
                "The county holds it in the owner’s name.",
            process = "A signed, notarized application is sent to the county auditor or treasurer with supporting documents.",
            deadline = "The county pays the owner on request within 3 years of receiving the funds.",
            ifMissed = "After 3 years the county moves the money into its own funds (in some counties, the land bank). " +
                "It is then usually no longer recoverable.",
            facilitator = "Surpay is a technology platform, not a law firm. It connects you with an independent licensed " +
                "attorney and tracks your case. The claim is made by you, through the attorney you choose, who is " +
                "responsible for the legal work. Surpay does not give legal advice and is not responsible for the " +
                "outcome of any claim.",
            proof = listOf(
                "A government photo ID (driver’s license, state ID or passport)",
                "Proof you owned the property when it was sold: the deed, a property tax bill, or the county record showing your name",
                "Proof you lived at or received mail at the property: utility bills, bank statements, insurance or tax records",
                "An IRS Form W-9 with your Social Security number, so the county can issue the payment",
            ),
            note = "This is general information, not legal advice.",
            constitutional = "Tyler v. Hennepin County (U.S. Supreme Court, 2023): keeping surplus beyond the debt owed is an unconstitutional taking.",
            sources = listOf("https://codes.ohio.gov/ohio-revised-code/section-5721.20"),
        )

        // Same steps and typical durations as backend/surpay/claims.py.
        private val STEPS = listOf(
            Triple("requested", "Claim started", 0 to 0),
            Triple("identity_submitted", "Identity submitted", 0 to 0),
            Triple("agreement_signed", "Agreement signed", 0 to 0),
            Triple("identity_verified", "Identity verified", 1 to 3),
            Triple("attorney_assigned", "Attorney assigned", 1 to 7),
            Triple("filed", "Claim filed", 7 to 21),
            Triple("hearing_pending", "Waiting for the county or court", 3 to 30),
            Triple("approved", "Hearing held and claim approved", 30 to 120),
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
