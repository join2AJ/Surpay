package com.surpay.app.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.first
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import retrofit2.HttpException
import java.io.IOException

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "surpay")
private val TOKEN = stringPreferencesKey("token")
private val SERVER_URL = stringPreferencesKey("server_url")

/** Which Surpay server the app talks to. Defaults to the URL baked in at build time. */
class ServerStore(private val context: Context, private val defaultUrl: String) {
    @Volatile var current: String = defaultUrl
        private set

    suspend fun load(): String = (context.dataStore.data.first()[SERVER_URL] ?: defaultUrl).also { current = it }

    suspend fun save(url: String) {
        val clean = url.trim().let { if (it.endsWith("/")) it else "$it/" }
        context.dataStore.edit { if (clean == defaultUrl) it.remove(SERVER_URL) else it[SERVER_URL] = clean }
        current = clean
    }
}

/** Stores the sign-in token on the device. */
class TokenStore(private val context: Context) {
    @Volatile var cached: String? = null
        private set

    suspend fun load(): String? = context.dataStore.data.first()[TOKEN].also { cached = it }

    suspend fun save(token: String) {
        context.dataStore.edit { it[TOKEN] = token }
        cached = token
    }

    suspend fun clear() {
        context.dataStore.edit { it.remove(TOKEN) }
        cached = null
    }
}

class SurpayRepository(private val api: SurpayApi, private val tokens: TokenStore) {
    suspend fun restoreSession(): Profile? {
        if (tokens.load() == null) return null
        return try {
            api.me()
        } catch (e: HttpException) {
            if (e.code() == 401) tokens.clear()
            null
        }
    }

    suspend fun signup(email: String, password: String, fullName: String): Profile =
        api.signup(SignupRequest(email.trim(), password, fullName.trim())).also { tokens.save(it.token) }.user

    suspend fun login(email: String, password: String): Profile =
        api.login(LoginRequest(email.trim(), password)).also { tokens.save(it.token) }.user

    /** Testing only: shared fictional account, reset on every demo sign-in. */
    suspend fun demoLogin(): Profile = api.demoLogin().also { tokens.save(it.token) }.user

    suspend fun logout() = tokens.clear()

    suspend fun updateProfile(update: ProfileUpdate): Profile = api.updateMe(update)
    suspend fun matches(): MatchesResponse = api.matches()
    suspend fun startClaim(recordId: Int): Claim = api.startClaim(ClaimRequest(recordId))
    suspend fun coverage(): Coverage = api.coverage()
}

/** Turn a network/HTTP failure into a sentence a person can act on. */
fun Throwable.userMessage(): String = when (this) {
    is HttpException -> {
        val detail = runCatching {
            val body = response()?.errorBody()?.string().orEmpty()
            when (val d = SurpayApi.json.decodeFromString<ApiError>(body).detail) {
                is JsonPrimitive -> d.contentOrNull
                // FastAPI validation errors: [{"msg": "...", "loc": [...]}, ...]
                is JsonArray -> d.mapNotNull { ((it as? JsonObject)?.get("msg") as? JsonPrimitive)?.contentOrNull }
                    .joinToString("\n")
                else -> null
            }
        }.getOrNull()
        detail?.takeIf { it.isNotBlank() } ?: "Something went wrong (error ${code()}). Please try again."
    }
    is IOException -> "Can't reach Surpay. Check your internet connection and try again."
    else -> message ?: "Something went wrong. Please try again."
}
