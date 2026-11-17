package com.intradaysathi.app

import org.junit.Assert.assertEquals
import org.junit.Test

class JsonTest {
    @Test
    fun jsonOfSkipsNullsAndKeepsNumbers() {
        val o = jsonOf("a" to 1, "b" to null, "c" to "x")
        assertEquals(1.0, o.dbl("a"), 0.0)
        assertEquals("", o.str("b"))
        assertEquals("x", o.str("c"))
    }

    @Test
    fun formatting() {
        assertEquals("₹1,234.50", money(1234.5))
    }

    @Test
    fun urlNormalising() {
        assertEquals("https://abc-8000.app.github.dev/", normalizeUrl("  abc-8000.app.github.dev/health "))
        assertEquals("https://abc-8000.app.github.dev/", normalizeUrl("https://abc-8000.app.github.dev"))
    }
}
