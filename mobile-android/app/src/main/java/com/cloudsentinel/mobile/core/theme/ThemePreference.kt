package com.cloudsentinel.mobile.core.theme

import android.content.Context

class ThemePreference(context: Context) {
    private val prefs = context.getSharedPreferences("cloudsentinel_theme", Context.MODE_PRIVATE)

    var mode: ThemeMode
        get() = runCatching {
            ThemeMode.valueOf(prefs.getString("mode", ThemeMode.LIGHT.name) ?: ThemeMode.LIGHT.name)
        }.getOrDefault(ThemeMode.LIGHT)
        set(value) {
            prefs.edit().putString("mode", value.name).apply()
        }
}
