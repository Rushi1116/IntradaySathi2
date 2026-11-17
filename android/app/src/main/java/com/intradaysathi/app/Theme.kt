package com.intradaysathi.app

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val DarkColors = darkColorScheme(
    primary = Color(0xFF4FD1A5), onPrimary = Color(0xFF00382A),
    secondary = Color(0xFF7AA2F7), background = Color(0xFF0E1116),
    surface = Color(0xFF161B22), surfaceVariant = Color(0xFF1F2630),
    onSurface = Color(0xFFE6EDF3), onBackground = Color(0xFFE6EDF3),
    onSurfaceVariant = Color(0xFF9AA7B4), error = Color(0xFFFF6B6B)
)

private val LightColors = lightColorScheme(
    primary = Color(0xFF0B7A5A), onPrimary = Color.White,
    secondary = Color(0xFF2F5FD0), background = Color(0xFFF4F6F8),
    surface = Color.White, surfaceVariant = Color(0xFFE8ECF0),
    onSurface = Color(0xFF14181D), onBackground = Color(0xFF14181D),
    onSurfaceVariant = Color(0xFF55616E), error = Color(0xFFC62828)
)

val Gain = Color(0xFF22A06B)
val Loss = Color(0xFFD64545)

@Composable
fun SathiTheme(dark: Boolean, content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = if (dark) DarkColors else LightColors, content = content)
}
