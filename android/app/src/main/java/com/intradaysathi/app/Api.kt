package com.intradaysathi.app

import com.google.gson.JsonObject
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.Response
import java.io.IOException
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query
import java.util.concurrent.TimeUnit

interface SathiApi {
    @GET("health") suspend fun health(): JsonObject
    @GET("disclaimer") suspend fun disclaimer(): JsonObject
    @GET("market/overview") suspend fun overview(): JsonObject
    @GET("stocks/search") suspend fun search(@Query("q") q: String): JsonObject
    @GET("candles/{symbol}") suspend fun candles(@Path("symbol") s: String, @Query("interval") i: String): JsonObject
    @GET("signals/{symbol}") suspend fun signal(@Path("symbol") s: String, @Query("interval") i: String): JsonObject
    @GET("signals") suspend fun signals(@Query("interval") i: String): JsonObject
    @GET("news") suspend fun news(@Query("symbol") s: String?): JsonObject
    @GET("fundamentals/{symbol}") suspend fun fundamentals(@Path("symbol") s: String): JsonObject
    @GET("announcements/{symbol}") suspend fun announcements(@Path("symbol") s: String): JsonObject
    @POST("paper/orders") suspend fun order(@Body body: JsonObject): JsonObject
    @POST("paper/positions/{id}/close") suspend fun closePosition(@Path("id") id: Int): JsonObject
    @GET("paper/portfolio") suspend fun portfolio(): JsonObject
    @GET("paper/trades") suspend fun trades(): JsonObject
    @POST("paper/reset") suspend fun resetAccount(): JsonObject
    @GET("auto/status") suspend fun autoStatus(): JsonObject
    @POST("auto/config") suspend fun autoConfig(@Body body: JsonObject): JsonObject
    @POST("auto/{action}") suspend fun autoAction(@Path("action") action: String): JsonObject
    @GET("ai/performance") suspend fun performance(): JsonObject
    @GET("ai/models") suspend fun models(): JsonObject
    @POST("ai/train") suspend fun train(@Query("interval") i: String): JsonObject
    @POST("ai/retrain") suspend fun retrain(@Query("interval") i: String): JsonObject
    @POST("ai/rollback") suspend fun rollback(@Query("interval") i: String): JsonObject

    companion object {
        fun create(baseUrl: String): SathiApi {
            val client = OkHttpClient.Builder()
                .addInterceptor(JsonGuardInterceptor())
                .connectTimeout(30, TimeUnit.SECONDS)
                .readTimeout(600, TimeUnit.SECONDS) // model training can take minutes
                .build()
            return Retrofit.Builder()
                .baseUrl(baseUrl)
                .client(client)
                .addConverterFactory(GsonConverterFactory.create())
                .build()
                .create(SathiApi::class.java)
        }
    }
}

/** Adds tunnel/JSON headers and turns "HTML instead of JSON" replies into a readable error. */
class JsonGuardInterceptor : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val req = chain.request().newBuilder()
            .header("Accept", "application/json")
            .header("X-Tunnel-Skip-AntiPhishing-Page", "true")
            .header("User-Agent", "IntradaySathi-Android/1.0")
            .build()
        val resp = chain.proceed(req)
        if (resp.isSuccessful) {
            val type = resp.header("Content-Type") ?: ""
            if (!type.contains("json", ignoreCase = true)) {
                val preview = resp.peekBody(400).string().replace(Regex("\\s+"), " ").take(220)
                resp.close()
                throw IOException("Backend did not return JSON (HTTP ${resp.code}, type '$type'). Received: $preview")
            }
        }
        return resp
    }
}

/** Accepts pasted URLs with spaces, missing https://, or extra paths like /health or /docs. */
fun normalizeUrl(input: String): String {
    var s = input.trim()
    require(s.isNotEmpty()) { "URL is empty" }
    if (!s.startsWith("http://") && !s.startsWith("https://")) s = "https://$s"
    val u = s.toHttpUrlOrNull() ?: throw IllegalArgumentException("Invalid URL")
    return u.newBuilder().encodedPath("/").query(null).fragment(null).build().toString()
}
