package com.intradaysathi.app

import android.app.Application
import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import retrofit2.HttpException

class AppVm(app: Application) : AndroidViewModel(app) {
    private val prefs = app.getSharedPreferences("sathi", Context.MODE_PRIVATE)
    private var api: SathiApi? = null
    private var apiUrl: String = ""

    var baseUrl by mutableStateOf(prefs.getString("url", "") ?: "")
    var dark by mutableStateOf(prefs.getBoolean("dark", true))
    var busy by mutableStateOf(0)
    var error by mutableStateOf<String?>(null)
    var message by mutableStateOf<String?>(null)
    var interval by mutableStateOf("5m")
    var disclaimer by mutableStateOf("")
    var overview by mutableStateOf(JsonObject())
    var signals by mutableStateOf<List<JsonObject>>(emptyList())
    var searchResults by mutableStateOf<List<JsonObject>>(emptyList())
    var selected by mutableStateOf<String?>(null)
    var candles by mutableStateOf<List<JsonObject>>(emptyList())
    var signal by mutableStateOf<JsonObject?>(null)
    var news by mutableStateOf<JsonObject?>(null)
    var fundamentals by mutableStateOf<JsonObject?>(null)
    var announcements by mutableStateOf<JsonObject?>(null)
    var portfolio by mutableStateOf<JsonObject?>(null)
    var trades by mutableStateOf<List<JsonObject>>(emptyList())
    var auto by mutableStateOf<JsonObject?>(null)
    var perf by mutableStateOf<JsonObject?>(null)
    var models by mutableStateOf<List<JsonObject>>(emptyList())

    private fun client(): SathiApi {
        if (baseUrl.isBlank()) throw IllegalStateException("Open Settings and enter your backend URL first.")
        val u = try {
            normalizeUrl(baseUrl)
        } catch (e: IllegalArgumentException) {
            throw IllegalStateException("Invalid backend URL. Paste the full https:// address.")
        }
        if (api == null || apiUrl != u) {
            api = SathiApi.create(u)
            apiUrl = u
        }
        return api!!
    }

    private fun detail(body: String?): String? = try {
        JsonParser.parseString(body ?: "").asJsonObject.get("detail").asString
    } catch (e: Exception) {
        body
    }

    private fun go(block: suspend (SathiApi) -> Unit) {
        viewModelScope.launch {
            busy += 1
            try {
                block(client())
                error = null
            } catch (e: CancellationException) {
                throw e
            } catch (e: HttpException) {
                error = "Server replied HTTP ${e.code()} " + (detail(e.response()?.errorBody()?.string()) ?: "").take(200)
            } catch (e: Exception) {
                error = e.message?.takeIf { it.isNotBlank() } ?: e.javaClass.simpleName
            } finally {
                busy -= 1
            }
        }
    }

    fun saveUrl(u: String) {
        baseUrl = try { normalizeUrl(u) } catch (e: IllegalArgumentException) { u.trim() }
        prefs.edit().putString("url", baseUrl).apply()
        refreshHome()
    }

    fun testConnection(u: String, onDone: (String) -> Unit) {
        viewModelScope.launch {
            val msg = try {
                val h = SathiApi.create(normalizeUrl(u)).health()
                if (h.str("status") == "ok") "Connected OK. NSE open now: ${h.bool("market_open")}" else "Unexpected reply: $h"
            } catch (e: CancellationException) {
                throw e
            } catch (e: HttpException) {
                "Failed: server replied HTTP ${e.code()}"
            } catch (e: Exception) {
                "Failed: ${e.message ?: e.javaClass.simpleName}"
            }
            onDone(msg)
        }
    }

    fun toggleTheme() {
        dark = !dark
        prefs.edit().putBoolean("dark", dark).apply()
    }

    fun onTab(i: Int) {
        message = null
        when (i) {
            0 -> refreshHome()
            1 -> search("")
            2 -> refreshPortfolio()
            3 -> refreshAuto()
            4 -> refreshAi()
        }
    }

    fun refreshHome() = go { a ->
        disclaimer = a.disclaimer().str("text")
        overview = a.overview()
        signals = a.signals(interval).list("items")
    }

    fun changeInterval(i: String) {
        interval = i
        if (selected != null) loadStock() else refreshHome()
    }

    fun search(q: String) = go { a -> searchResults = a.search(q).list("items") }

    fun openStock(s: String) {
        selected = s
        loadStock()
    }

    fun closeStock() {
        selected = null
    }

    fun loadStock() {
        val s = selected ?: return
        candles = emptyList(); signal = null
        go { a -> candles = a.candles(s, interval).list("items") }
        go { a -> signal = a.signal(s, interval) }
        go { a -> news = a.news(s) }
        go { a -> fundamentals = a.fundamentals(s) }
        go { a -> announcements = a.announcements(s) }
    }

    fun placeOrder(side: String, qty: Int) = go { a ->
        val s = selected ?: return@go
        val lv = signal?.obj("levels")?.obj(side.lowercase())
        val body = jsonOf(
            "symbol" to s, "side" to side, "qty" to qty, "interval" to interval,
            "stop_loss" to lv?.dbl("stop_loss"), "target" to lv?.dbl("target")
        )
        val t = a.order(body)
        message = "Paper $side ${t.str("qty")} $s @ ${money(t.dbl("entry"))} (SL ${money(t.dbl("stop_loss"))}, target ${money(t.dbl("target"))})"
    }

    fun refreshPortfolio() = go { a ->
        portfolio = a.portfolio()
        trades = a.trades().list("items")
    }

    fun closePosition(id: Int) = go { a ->
        val t = a.closePosition(id)
        message = "Closed ${t.str("symbol")} P&L ${money(t.dbl("pnl"))}"
        portfolio = a.portfolio()
        trades = a.trades().list("items")
    }

    fun resetAccount() = go { a ->
        message = a.resetAccount().str("message")
        portfolio = a.portfolio()
        trades = a.trades().list("items")
    }

    fun refreshAuto() = go { a -> auto = a.autoStatus() }

    fun autoAction(action: String) = go { a -> auto = a.autoAction(action) }

    fun saveAutoConfig(loss: String, maxTrades: String, conf: String) = go { a ->
        a.autoConfig(
            jsonOf(
                "daily_loss_limit" to loss.toDoubleOrNull(),
                "max_trades" to maxTrades.toIntOrNull(),
                "min_confidence" to conf.toDoubleOrNull()
            )
        )
        auto = a.autoStatus()
        message = "Automation settings saved."
    }

    fun refreshAi() = go { a ->
        perf = a.performance()
        models = a.models().list("items")
    }

    fun train() = go { a ->
        val r = a.train(interval)
        message = "Trained ${r.str("version")}: validation accuracy ${r.dbl("accuracy")} (majority baseline ${r.dbl("baseline_accuracy")}), activated=${r.bool("activated")}"
        models = a.models().list("items")
    }

    fun retrain() = go { a ->
        val r = a.retrain(interval)
        message = if (r.bool("retrained")) "Retrained ${r.str("version")} (activated=${r.bool("activated")})" else r.str("reason")
        models = a.models().list("items")
    }

    fun rollback() = go { a ->
        val r = a.rollback(interval)
        message = "Rolled back to ${r.str("version")}"
        models = a.models().list("items")
    }
}
