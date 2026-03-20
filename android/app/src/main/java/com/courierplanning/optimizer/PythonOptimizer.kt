package com.courierplanning.optimizer

import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import android.content.Context
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject

object PythonOptimizer {
    private val json = Json { ignoreUnknownKeys = true }

    fun ensureStarted(context: Context) {
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(context))
        }
    }

    /**
     * Calls courierpy.optimizer_bridge.optimize_route_json(payloadJson) and returns parsed JSON.
     */
    fun optimize(payloadJson: String): JsonObject {
        val py = Python.getInstance()
        val module = py.getModule("courierpy.optimizer_bridge")
        val result = module.callAttr("optimize_route_json", payloadJson).toString()
        return json.parseToJsonElement(result).jsonObject
    }

    fun ping(): String {
        val py = Python.getInstance()
        val module = py.getModule("courierpy.optimizer_bridge")
        return module.callAttr("ping").toString()
    }
}

