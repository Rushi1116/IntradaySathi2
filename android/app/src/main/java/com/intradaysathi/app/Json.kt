package com.intradaysathi.app

import com.google.gson.JsonObject
import com.google.gson.JsonPrimitive

fun JsonObject.str(k: String): String {
    val e = get(k)
    return if (e == null || e.isJsonNull || !e.isJsonPrimitive) "" else e.asString
}

fun JsonObject.dbl(k: String): Double {
    val e = get(k)
    return if (e == null || e.isJsonNull || !e.isJsonPrimitive) 0.0 else e.asString.toDoubleOrNull() ?: 0.0
}

fun JsonObject.bool(k: String): Boolean {
    val e = get(k)
    return e != null && e.isJsonPrimitive && e.asString == "true"
}

fun JsonObject.obj(k: String): JsonObject? {
    val e = get(k)
    return if (e != null && e.isJsonObject) e.asJsonObject else null
}

fun JsonObject.list(k: String): List<JsonObject> {
    val e = get(k)
    return if (e != null && e.isJsonArray) e.asJsonArray.filter { it.isJsonObject }.map { it.asJsonObject } else emptyList()
}

fun JsonObject.strings(k: String): List<String> {
    val e = get(k)
    return if (e != null && e.isJsonArray) e.asJsonArray.map { it.asString } else emptyList()
}

fun jsonOf(vararg pairs: Pair<String, Any?>): JsonObject {
    val o = JsonObject()
    for ((k, v) in pairs) {
        when (v) {
            null -> {}
            is Number -> o.addProperty(k, v)
            is Boolean -> o.addProperty(k, v)
            else -> o.add(k, JsonPrimitive(v.toString()))
        }
    }
    return o
}

fun money(v: Double): String = "₹" + String.format("%,.2f", v)
fun pct(v: Double): String = String.format("%+.2f%%", v)
