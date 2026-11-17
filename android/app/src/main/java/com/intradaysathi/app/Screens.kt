package com.intradaysathi.app

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.clickable
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.AccountBalanceWallet
import androidx.compose.material.icons.filled.DarkMode
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Insights
import androidx.compose.material.icons.filled.LightMode
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.SmartToy
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.google.gson.JsonObject
import kotlin.math.abs

private val tabs = listOf(
    "Home" to Icons.Filled.Home, "Stocks" to Icons.Filled.Search,
    "Portfolio" to Icons.Filled.AccountBalanceWallet, "Auto" to Icons.Filled.SmartToy,
    "AI" to Icons.Filled.Insights
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SathiApp(vm: AppVm) {
    var tab by remember { mutableIntStateOf(0) }
    var showSettings by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) {
        if (vm.baseUrl.isBlank()) showSettings = true else vm.refreshHome()
    }
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(vm.selected ?: "Intraday Sathi", fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    if (vm.selected != null) IconButton(onClick = { vm.closeStock() }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(onClick = { vm.toggleTheme() }) {
                        Icon(if (vm.dark) Icons.Filled.LightMode else Icons.Filled.DarkMode, contentDescription = "Theme")
                    }
                    IconButton(onClick = { showSettings = true }) {
                        Icon(Icons.Filled.Settings, contentDescription = "Settings")
                    }
                }
            )
        },
        bottomBar = {
            NavigationBar {
                tabs.forEachIndexed { i, (label, icon) ->
                    NavigationBarItem(
                        selected = tab == i,
                        onClick = { tab = i; vm.closeStock(); vm.onTab(i) },
                        icon = { Icon(icon, contentDescription = label) },
                        label = { Text(label) }
                    )
                }
            }
        }
    ) { pad ->
        Column(Modifier.padding(pad).fillMaxSize()) {
            if (vm.busy > 0) LinearProgressIndicator(Modifier.fillMaxWidth())
            vm.error?.let { Banner(it, true) }
            vm.message?.let { Banner(it, false) }
            if (vm.selected != null) StockDetail(vm) else when (tab) {
                0 -> HomeScreen(vm)
                1 -> StocksScreen(vm)
                2 -> PortfolioScreen(vm)
                3 -> AutoScreen(vm)
                else -> AiScreen(vm)
            }
        }
    }
    if (showSettings) SettingsDialog(vm) { showSettings = false }
}

@Composable
fun Banner(text: String, isError: Boolean) {
    Card(
        Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (isError) MaterialTheme.colorScheme.error.copy(alpha = 0.18f)
            else MaterialTheme.colorScheme.primary.copy(alpha = 0.18f)
        )
    ) { Text(text, Modifier.padding(10.dp), style = MaterialTheme.typography.bodySmall) }
}

@Composable
fun SettingsDialog(vm: AppVm, onClose: () -> Unit) {
    var url by remember { mutableStateOf(vm.baseUrl) }
    var result by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onClose,
        title = { Text("Backend URL") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    "Paste the public URL of your Intraday Sathi backend, e.g. https://your-codespace-8000.app.github.dev/",
                    style = MaterialTheme.typography.bodySmall
                )
                OutlinedTextField(url, { url = it }, singleLine = true, label = { Text("https://...") })
                OutlinedButton({ result = "Testing..."; vm.testConnection(url) { result = it } }) { Text("Test connection") }
                if (result.isNotBlank()) Text(result, style = MaterialTheme.typography.bodySmall)
            }
        },
        confirmButton = { TextButton(onClick = { vm.saveUrl(url); onClose() }) { Text("Save") } },
        dismissButton = { TextButton(onClick = onClose) { Text("Close") } }
    )
}

@Composable
fun Panel(title: String, content: @Composable ColumnScope.() -> Unit) {
    Card(
        Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(title, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
            content()
        }
    }
}

@Composable
fun Screen(content: @Composable ColumnScope.() -> Unit) {
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
        content = content
    )
}

@Composable
fun KV(k: String, v: String, color: Color = Color.Unspecified) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(k, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
        Text(v, color = color, fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodyMedium)
    }
}

fun pnlColor(v: Double): Color = if (v >= 0) Gain else Loss
fun sigColor(s: String): Color = when (s) { "BUY" -> Gain; "SELL" -> Loss; else -> Color(0xFF9AA7B4) }

@Composable
fun IntervalChips(vm: AppVm) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        listOf("5m", "15m").forEach { i ->
            FilterChip(selected = vm.interval == i, onClick = { vm.changeInterval(i) }, label = { Text(i) })
        }
    }
}

@Composable
fun SignalRow(s: JsonObject, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clickable { onClick() }.padding(vertical = 6.dp),
        horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically
    ) {
        Column {
            Text(s.str("symbol"), fontWeight = FontWeight.SemiBold)
            Text(money(s.dbl("price")), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Column(horizontalAlignment = Alignment.End) {
            Text(s.str("signal"), color = sigColor(s.str("signal")), fontWeight = FontWeight.Bold)
            Text("conf ${(s.dbl("confidence") * 100).toInt()}%" + if (s.str("model_type") != "xgboost") " (rules)" else "",
                style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
fun HomeScreen(vm: AppVm) = Screen {
    Panel("Risk disclosure") {
        Text(
            vm.disclaimer.ifBlank { "Paper trading only. Data is delayed. AI signals are not advice and have no guaranteed accuracy or profit." },
            style = MaterialTheme.typography.bodySmall
        )
    }
    Panel("Market overview") {
        val items = vm.overview.list("items")
        if (items.isEmpty()) Text("No data yet. Check backend URL in Settings.")
        items.forEach {
            val unavailable = it.bool("unavailable")
            KV(it.str("name"), if (unavailable) "unavailable" else "${String.format("%,.2f", it.dbl("price"))}  ${pct(it.dbl("change_pct"))}",
                if (unavailable) Color.Unspecified else pnlColor(it.dbl("change_pct")))
        }
        Text(if (vm.overview.bool("market_open")) "NSE is open (data delayed ~15 min)" else "NSE is closed; showing last available data",
            style = MaterialTheme.typography.bodySmall)
    }
    Panel("Watchlist AI signals") {
        IntervalChips(vm)
        if (vm.signals.isEmpty()) Text("No signals yet (loading, or data unavailable).")
        vm.signals.forEach { SignalRow(it) { vm.openStock(it.str("symbol")) } }
        Text("Without a trained model, signals use simple rules. Train a model in the AI tab.", style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
fun StocksScreen(vm: AppVm) {
    var q by remember { mutableStateOf("") }
    Column(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        OutlinedTextField(
            q, { q = it; vm.search(it) }, Modifier.fillMaxWidth(), singleLine = true,
            label = { Text("Search NSE stock (e.g. RELIANCE)") }
        )
        Column(Modifier.verticalScroll(rememberScrollState())) {
            vm.searchResults.forEach {
                Row(Modifier.fillMaxWidth().clickable { vm.openStock(it.str("symbol")) }.padding(vertical = 10.dp)) {
                    Text(it.str("symbol"), fontWeight = FontWeight.SemiBold, modifier = Modifier.width(120.dp))
                    Text(it.str("name"), style = MaterialTheme.typography.bodyMedium)
                }
            }
        }
    }
}

@Composable
fun CandleChart(candles: List<JsonObject>, modifier: Modifier) {
    val up = Gain
    val down = Loss
    val vwapColor = Color(0xFFF5A623)
    val emaColor = Color(0xFF7AA2F7)
    Canvas(modifier) {
        if (candles.isEmpty()) return@Canvas
        val n = candles.size
        val hi = candles.maxOf { it.dbl("h") }
        val lo = candles.minOf { it.dbl("l") }
        val range = (hi - lo).coerceAtLeast(1e-6)
        val w = size.width / n
        fun y(v: Double): Float = ((hi - v) / range * size.height).toFloat()
        candles.forEachIndexed { i, c ->
            val col = if (c.dbl("c") >= c.dbl("o")) up else down
            val x = i * w + w / 2
            drawLine(col, Offset(x, y(c.dbl("h"))), Offset(x, y(c.dbl("l"))), strokeWidth = 1.5f)
            val top = y(maxOf(c.dbl("o"), c.dbl("c")))
            val bh = abs(y(c.dbl("o")) - y(c.dbl("c"))).coerceAtLeast(1.5f)
            drawRect(col, Offset(i * w + w * 0.15f, top), Size(w * 0.7f, bh))
        }
        fun line(key: String, color: Color) {
            val p = Path()
            candles.forEachIndexed { i, c ->
                val x = i * w + w / 2
                val yy = y(c.dbl(key).coerceIn(lo, hi))
                if (i == 0) p.moveTo(x, yy) else p.lineTo(x, yy)
            }
            drawPath(p, color, style = Stroke(width = 2f))
        }
        line("vwap", vwapColor)
        line("ema21", emaColor)
    }
}

@Composable
fun StockDetail(vm: AppVm) {
    var qty by remember { mutableStateOf("10") }
    Screen {
        IntervalChips(vm)
        Panel("Chart (${vm.interval}) · yellow=VWAP, blue=EMA21") {
            CandleChart(vm.candles.takeLast(80), Modifier.fillMaxWidth().height(220.dp))
            vm.candles.lastOrNull()?.let {
                KV("RSI", String.format("%.1f", it.dbl("rsi")))
                KV("MACD", String.format("%.3f", it.dbl("macd")))
                KV("ATR", String.format("%.2f", it.dbl("atr")))
                KV("Volume vs avg", String.format("%.2fx", it.dbl("vol_ratio")))
                KV("Last bar", it.str("t").take(16).replace("T", " "))
            }
            if (vm.candles.isEmpty()) Text("Candles unavailable or loading.")
        }
        Panel("AI signal") {
            val s = vm.signal
            if (s == null) Text("Loading or unavailable.") else {
                val sig = s.str("signal")
                Text(sig, color = sigColor(sig), style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                KV("Confidence (model score)", "${(s.dbl("confidence") * 100).toInt()}%")
                KV("Price (delayed)", money(s.dbl("price")))
                val side = if (sig == "SELL") "sell" else "buy"
                val lv = s.obj("levels")?.obj(side)
                if (sig != "HOLD" && lv != null) {
                    KV("Stop-loss", money(lv.dbl("stop_loss")))
                    KV("Target", money(lv.dbl("target")))
                    KV("Risk:Reward", "1 : ${s.dbl("risk_reward")}")
                }
                Text("Model: ${s.str("model_type")} ${s.str("model_version")}. ${s.str("note")}", style = MaterialTheme.typography.bodySmall)
            }
        }
        Panel("Paper order (virtual money)") {
            OutlinedTextField(
                qty, { qty = it.filter(Char::isDigit) }, label = { Text("Quantity") }, singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number)
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button({ vm.placeOrder("BUY", qty.toIntOrNull() ?: 0) }, colors = ButtonDefaults.buttonColors(containerColor = Gain)) { Text("Paper BUY") }
                Button({ vm.placeOrder("SELL", qty.toIntOrNull() ?: 0) }, colors = ButtonDefaults.buttonColors(containerColor = Loss)) { Text("Paper SELL") }
            }
            Text("Uses the AI signal's stop-loss and target when available. No real orders are ever placed.", style = MaterialTheme.typography.bodySmall)
        }
        Panel("Fundamentals") {
            val f = vm.fundamentals
            if (f == null) Text("Loading...") else if (!f.bool("available")) Text(f.str("message").ifBlank { "Unavailable" }) else {
                val d = f.obj("data")
                listOf("name", "sector", "industry", "market_cap", "pe", "pb", "roe", "debt_to_equity", "profit_margin", "dividend_yield", "week52_high", "week52_low", "beta").forEach {
                    val v = d?.get(it)
                    KV(it.replace("_", " "), if (v == null || v.isJsonNull) "n/a" else v.asString)
                }
                Text("Source: ${f.str("source")}", style = MaterialTheme.typography.bodySmall)
            }
        }
        Panel("News & sentiment") {
            val n = vm.news
            if (n == null) Text("Loading...") else {
                if (n.str("message").isNotBlank()) Text(n.str("message"), style = MaterialTheme.typography.bodySmall)
                if (n.bool("available")) KV("Avg headline sentiment", String.format("%+.2f", n.dbl("avg_sentiment")), pnlColor(n.dbl("avg_sentiment")))
                n.list("items").take(8).forEach {
                    Column(Modifier.padding(vertical = 4.dp)) {
                        Text(it.str("title"), style = MaterialTheme.typography.bodyMedium)
                        Text("${it.str("source")} · ${it.obj("sentiment")?.str("label") ?: ""}", style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
        Panel("NSE announcements") {
            val a = vm.announcements
            if (a == null) Text("Loading...") else if (!a.bool("available")) Text(a.str("message")) else {
                a.list("items").take(8).forEach {
                    Column(Modifier.padding(vertical = 4.dp)) {
                        Text(it.str("subject"), style = MaterialTheme.typography.bodyMedium)
                        Text(it.str("date"), style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}

@Composable
fun PortfolioScreen(vm: AppVm) = Screen {
    val p = vm.portfolio
    if (p == null) Text("Loading portfolio...") else {
        Panel("Virtual account") {
            KV("Equity", money(p.dbl("equity")))
            KV("Cash", money(p.dbl("cash")))
            KV("Invested / margin blocked", money(p.dbl("invested")))
            KV("Unrealized P&L", money(p.dbl("unrealized_pnl")), pnlColor(p.dbl("unrealized_pnl")))
            KV("Realized P&L", money(p.dbl("realized_pnl")), pnlColor(p.dbl("realized_pnl")))
            KV("Today P&L", money(p.dbl("today_pnl")), pnlColor(p.dbl("today_pnl")))
            KV("Total return", pct(p.dbl("total_return_pct")), pnlColor(p.dbl("total_return_pct")))
        }
        Panel("Open positions") {
            val pos = p.list("positions")
            if (pos.isEmpty()) Text("No open positions.")
            pos.forEach {
                Column(Modifier.padding(vertical = 4.dp)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Text("${it.str("side")} ${it.str("qty")} ${it.str("symbol")} (${it.str("source")})", fontWeight = FontWeight.SemiBold)
                        OutlinedButton({ vm.closePosition(it.dbl("id").toInt()) }) { Text("Close") }
                    }
                    Text("Entry ${money(it.dbl("entry"))} · LTP ${money(it.dbl("ltp"))} · SL ${money(it.dbl("stop_loss"))} · TGT ${money(it.dbl("target"))}",
                        style = MaterialTheme.typography.bodySmall)
                    Text("P&L ${money(it.dbl("unrealized_pnl"))}", color = pnlColor(it.dbl("unrealized_pnl")), style = MaterialTheme.typography.bodyMedium)
                }
            }
        }
        Panel("Trade history") {
            if (vm.trades.none { it.str("status") == "CLOSED" }) Text("No completed trades.")
            vm.trades.filter { it.str("status") == "CLOSED" }.take(25).forEach {
                KV("${it.str("side")} ${it.str("symbol")} (${it.str("exit_reason")})", money(it.dbl("pnl")), pnlColor(it.dbl("pnl")))
            }
        }
        OutlinedButton({ vm.resetAccount() }, Modifier.fillMaxWidth()) { Text("Reset virtual account to ₹1,00,000") }
    }
}

@Composable
fun AutoScreen(vm: AppVm) {
    val a = vm.auto
    var loss by remember { mutableStateOf("") }
    var maxT by remember { mutableStateOf("") }
    var conf by remember { mutableStateOf("") }
    LaunchedEffect(a?.obj("config")) {
        a?.obj("config")?.let {
            loss = it.dbl("daily_loss_limit").toInt().toString()
            maxT = it.dbl("max_trades").toInt().toString()
            conf = it.dbl("min_confidence").toString()
        }
    }
    Screen {
        if (a == null) Text("Loading...") else {
            val st = a.str("status")
            Panel("Automated paper trading") {
                Text(st.uppercase(), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold,
                    color = if (st == "running") Gain else if (st == "emergency") Loss else MaterialTheme.colorScheme.onSurface)
                if (a.str("halt_reason").isNotBlank()) Text(a.str("halt_reason"), color = Loss)
                KV("Trades today", a.str("trades_today"))
                KV("Open positions", a.str("open_positions"))
                KV("Today P&L", money(a.dbl("today_pnl")), pnlColor(a.dbl("today_pnl")))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button({ vm.autoAction("start") }) { Text("Start") }
                    OutlinedButton({ vm.autoAction("pause") }) { Text("Pause") }
                    OutlinedButton({ vm.autoAction("resume") }) { Text("Resume") }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton({ vm.autoAction("stop") }) { Text("Stop") }
                    Button({ vm.autoAction("emergency") }, colors = ButtonDefaults.buttonColors(containerColor = Loss)) { Text("EMERGENCY STOP") }
                }
                Text("Emergency stop closes all paper positions immediately. New entries run only 09:20-15:00 IST on weekdays and need a trained model. All positions are squared off at 15:15.",
                    style = MaterialTheme.typography.bodySmall)
            }
            Panel("Risk limits") {
                OutlinedTextField(loss, { loss = it }, label = { Text("Daily loss limit (₹)") }, singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number))
                OutlinedTextField(maxT, { maxT = it }, label = { Text("Max trades per day") }, singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number))
                OutlinedTextField(conf, { conf = it }, label = { Text("Min confidence (0.34-0.99)") }, singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal))
                Button({ vm.saveAutoConfig(loss, maxT, conf) }) { Text("Save limits") }
                Text("Watchlist: " + a.obj("config")?.strings("watchlist")?.joinToString(", "), style = MaterialTheme.typography.bodySmall)
            }
            Panel("Activity log") {
                val log = a.strings("log")
                if (log.isEmpty()) Text("No activity yet.")
                log.take(20).forEach { Text(it, style = MaterialTheme.typography.bodySmall) }
            }
            OutlinedButton({ vm.refreshAuto() }, Modifier.fillMaxWidth()) { Text("Refresh") }
        }
    }
}

@Composable
fun AiScreen(vm: AppVm) = Screen {
    val p = vm.perf
    Panel("AI evolution (paper trades)") {
        if (p == null) Text("Loading...") else {
            KV("Completed trades", p.str("total_trades"))
            KV("Win rate", "${p.dbl("win_rate")}%")
            KV("AI trade accuracy", if (p.str("ai_trade_accuracy").isBlank()) "n/a" else "${p.dbl("ai_trade_accuracy")}% (${p.str("ai_trades")} trades)")
            KV("Profit factor", if (p.str("profit_factor").isBlank()) "n/a" else p.str("profit_factor"))
            KV("Max drawdown", "${money(p.dbl("max_drawdown"))} (${p.dbl("max_drawdown_pct")}%)")
            KV("Total P&L", money(p.dbl("total_pnl")), pnlColor(p.dbl("total_pnl")))
            Text(p.str("note"), style = MaterialTheme.typography.bodySmall)
        }
    }
    if (p != null) {
        listOf("daily" to "Daily P&L", "weekly" to "Weekly P&L", "monthly" to "Monthly P&L").forEach { (k, title) ->
            Panel(title) {
                val l = p.list(k)
                if (l.isEmpty()) Text("No data yet.")
                l.reversed().take(10).forEach { KV("${it.str("period")} (${it.str("trades")})", money(it.dbl("pnl")), pnlColor(it.dbl("pnl"))) }
            }
        }
    }
    Panel("Model versions") {
        IntervalChips(vm)
        if (vm.models.isEmpty()) Text("No trained model yet. Tap Train (takes 1-3 minutes). Until then signals are rule-based.")
        vm.models.forEach {
            Column(Modifier.padding(vertical = 3.dp)) {
                Text("${it.str("version")}  ${if (it.dbl("active") == 1.0) "● ACTIVE" else ""}", fontWeight = FontWeight.SemiBold)
                Text("val accuracy ${String.format("%.1f", it.dbl("accuracy") * 100)}% · samples ${it.str("samples")}", style = MaterialTheme.typography.bodySmall)
                Text(it.str("notes"), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button({ vm.train() }) { Text("Train ${vm.interval}") }
            OutlinedButton({ vm.retrain() }) { Text("Retrain") }
            OutlinedButton({ vm.rollback() }) { Text("Rollback") }
        }
        Text("Models are validated on recent held-out data and only activated if not worse than the current model. Accuracy near the majority baseline means little predictive skill. Retrain needs enough completed AI paper trades. Past accuracy does not guarantee future results.",
            style = MaterialTheme.typography.bodySmall)
    }
    OutlinedButton({ vm.refreshAi() }, Modifier.fillMaxWidth()) { Text("Refresh") }
}
