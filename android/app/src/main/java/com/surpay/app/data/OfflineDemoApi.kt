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
    private val claims = mutableMapOf<Int, Claim>()

    private fun freshProfile() = Profile(
        id = 0, email = "demo@surpay.test", fullName = DEMO_NAME,
        addresses = listOf(Address(id = 1, street = "412 Maple Ridge Rd", city = "Springfield", state = "OH", zip = "45501")),
    )

    /** Start over, like the server does on every demo sign-in. */
    fun reset() {
        profile = freshProfile()
        claims.clear()
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
                saleDate = r.sold, sourceUrl = "", lastSeen = now, claimStatus = claims[r.id]?.status,
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

    override suspend fun startClaim(body: ClaimRequest): Claim {
        val r = records.first { it.id == body.recordId }
        return claims.getOrPut(r.id) {
            Claim(claims.size + 1, r.id, "requested", "Demo", "OH", r.ref, r.cents, now, now)
        }
    }

    override suspend fun claims(): List<Claim> = claims.values.toList()

    override suspend fun signup(body: SignupRequest): TokenResponse = offline()
    override suspend fun login(body: LoginRequest): TokenResponse = offline()

    private fun offline(): Nothing =
        throw IllegalStateException("You're in the offline demo. Sign out to create a real account.")

    companion object {
        const val OFFLINE_DEMO_TOKEN = "offline-demo"
        const val DEMO_NAME = "Jordan Testwell"
    }
}
