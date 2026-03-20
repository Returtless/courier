package com.courierplanning.settings

import android.content.Context
import android.content.SharedPreferences

data class StartLocationConfig(
    val startLat: Double,
    val startLon: Double,
    val startTimeLocal: String, // "HH:mm"
)

object StartLocationPrefs {
    private const val PREFS_NAME = "courier_start_config"
    private const val KEY_LAT = "start_lat"
    private const val KEY_LON = "start_lon"
    private const val KEY_TIME = "start_time_local"

    private fun prefs(context: Context): SharedPreferences =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun load(context: Context): StartLocationConfig {
        val p = prefs(context)
        val lat = java.lang.Double.longBitsToDouble(
            p.getLong(KEY_LAT, java.lang.Double.doubleToRawLongBits(59.93)),
        )
        val lon = java.lang.Double.longBitsToDouble(
            p.getLong(KEY_LON, java.lang.Double.doubleToRawLongBits(30.31)),
        )
        val time = p.getString(KEY_TIME, "09:00") ?: "09:00"
        return StartLocationConfig(lat, lon, time)
    }

    fun save(context: Context, config: StartLocationConfig) {
        prefs(context).edit()
            .putLong(KEY_LAT, java.lang.Double.doubleToRawLongBits(config.startLat))
            .putLong(KEY_LON, java.lang.Double.doubleToRawLongBits(config.startLon))
            .putString(KEY_TIME, config.startTimeLocal)
            .apply()
    }
}

