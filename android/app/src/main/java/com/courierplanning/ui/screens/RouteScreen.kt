package com.courierplanning.ui.screens

import android.content.Context
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.courierplanning.AppServices
import com.courierplanning.BuildConfig
import com.courierplanning.data.db.CallStatusEntity
import com.courierplanning.data.db.OrderEntity
import com.courierplanning.data.db.RouteEntity
import com.courierplanning.data.db.RoutePointEntity
import com.courierplanning.optimizer.PythonOptimizer
import com.courierplanning.settings.StartLocationPrefs
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.time.Instant
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.time.LocalDate
import java.time.format.DateTimeFormatter

private val json = Json { ignoreUnknownKeys = true }

@Composable
fun RouteScreen(onBack: () -> Unit) {
    val context = LocalContext.current
    val today = remember { LocalDate.now() }
    val todayIso = remember { today.toString() }
    val formattedDate = remember { today.format(DateTimeFormatter.ofPattern("dd.MM.yyyy")) }
    val startCfg = remember { StartLocationPrefs.load(context) }
    var route by remember { mutableStateOf<RouteEntity?>(null) }
    var points by remember { mutableStateOf<List<RoutePointEntity>>(emptyList()) }
    var isBuilding by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(todayIso) {
        val (r, p) = loadRouteData(todayIso)
        route = r
        points = p
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            text = buildString {
                append(formattedDate)
                append(" · старт ${startCfg.startTimeLocal}")
                if (points.isNotEmpty()) {
                    append(" · ${points.size} точек")
                }
            },
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        error?.let {
            Text(
                text = "Ошибка: $it",
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
            )
        }
        if (isBuilding) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                CircularProgressIndicator()
                Spacer(Modifier.width(8.dp))
                Text("Строим маршрут...")
            }
        } else {
            OutlinedButton(
                onClick = {
                    isBuilding = true
                    error = null
                    scope.launch(Dispatchers.IO) {
                        try {
                            buildAndSaveRoute(context, todayIso)
                            val (r, p) = loadRouteData(todayIso)
                            withContext(Dispatchers.Main) {
                                route = r
                                points = p
                            }
                        } catch (e: Exception) {
                            withContext(Dispatchers.Main) {
                                error = e.message ?: e.toString()
                            }
                        } finally {
                            withContext(Dispatchers.Main) { isBuilding = false }
                        }
                    }
                },
                shape = RoundedCornerShape(12.dp),
            ) { Text("Построить маршрут") }
        }
        if (route != null && points.isNotEmpty()) {
            Spacer(Modifier.height(8.dp))
            Card(
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surfaceVariant,
                ),
                elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(12.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    Text(
                        text = "Завершение: ${route!!.estimatedCompletionIso}",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    Text(
                        text = "Дистанция: ${route!!.totalDistanceKm} км",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        text = "Время в пути: ${route!!.totalTimeMin} мин",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            Spacer(Modifier.height(8.dp))
            LazyColumn(
                verticalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                items(points, key = { it.id }) { p ->
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(
                            containerColor = MaterialTheme.colorScheme.surface,
                        ),
                        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
                    ) {
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(12.dp),
                            verticalArrangement = Arrangement.spacedBy(4.dp),
                        ) {
                            Text(
                                text = "${p.position}. №${p.orderNumber}",
                                style = MaterialTheme.typography.bodyMedium,
                            )
                            Text(
                                text = "Прибытие: ${p.estimatedArrivalIso.take(16)}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            p.windowEnd?.let {
                                Text(
                                    text = "Окно до $it",
                                    style = MaterialTheme.typography.bodySmall,
                                )
                            }
                            if (p.isLate) {
                                Text(
                                    text = "Позже окна",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.error,
                                )
                            }
                        }
                    }
                }
            }
        } else if (!isBuilding) {
            Spacer(Modifier.height(16.dp))
            Text(
                "Нет маршрута. Добавьте заказы на экране «Заказы» и нажмите «Построить маршрут».",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

private suspend fun loadRouteData(routeDate: String): Pair<RouteEntity?, List<RoutePointEntity>> =
    withContext(Dispatchers.IO) {
        val r = AppServices.db.routesDao().getByDate(routeDate)
        val p = r?.let { AppServices.db.routePointsDao().list(it.id) } ?: emptyList()
        r to p
    }

private suspend fun buildAndSaveRoute(context: Context, routeDate: String) {
    val db = AppServices.db
    val orders = db.ordersDao().listByDate(routeDate)
    if (orders.isEmpty()) throw IllegalStateException("Нет заказов на $routeDate")
    val settings = db.settingsDao().get() ?: com.courierplanning.data.db.SettingsEntity()
    val callAdvanceMinutes = settings.callAdvanceMinutes
    val startCfg = StartLocationPrefs.load(context)
    val startTime = "${routeDate}T${startCfg.startTimeLocal}:00+03:00"
    val startLat = startCfg.startLat
    val startLon = startCfg.startLon
    val payload = buildPayload(orders, startLat, startLon, startTime, settings.serviceTimeMinutes)
    PythonOptimizer.ensureStarted(context)
    val result = PythonOptimizer.optimize(payload)
    val routePointsJson = result["route_points"]!!.jsonArray
    val totalDistanceKm = result["total_distance_km"]?.jsonPrimitive?.content?.toDoubleOrNull() ?: 0.0
    val totalTimeMin = result["total_time_min"]?.jsonPrimitive?.content?.toDoubleOrNull() ?: 0.0
    val estimatedCompletionIso = result["estimated_completion_iso"]?.jsonPrimitive?.content ?: startTime

    val existing = db.routesDao().getByDate(routeDate)
    if (existing != null) {
        db.routePointsDao().deleteByRouteId(existing.id)
        db.routesDao().deleteByDate(routeDate)
    }
    val routeId = db.routesDao().insert(
        RouteEntity(
            routeDate = routeDate,
            startLat = startLat,
            startLon = startLon,
            startTimeIso = startTime,
            totalDistanceKm = totalDistanceKm,
            totalTimeMin = totalTimeMin,
            estimatedCompletionIso = estimatedCompletionIso,
        ),
    )
    val orderByNumber = orders.associateBy { it.orderNumber }
    val points = routePointsJson.mapIndexed { idx, el ->
        val o = el.jsonObject
        val orderNumber = o["order_number"]?.jsonPrimitive?.content ?: ""
        val estimatedArrivalIso = o["estimated_arrival_iso"]?.jsonPrimitive?.content ?: ""
        val callTimeIso = o["call_time_iso"]?.jsonPrimitive?.content
        RoutePointEntity(
            routeId = routeId,
            position = idx + 1,
            orderNumber = orderNumber,
            estimatedArrivalIso = estimatedArrivalIso,
            callTimeIso = callTimeIso,
            distanceFromPreviousKm = o["distance_from_previous_km"]?.jsonPrimitive?.content?.toDoubleOrNull() ?: 0.0,
            timeFromPreviousMin = o["time_from_previous_min"]?.jsonPrimitive?.content?.toDoubleOrNull() ?: 0.0,
            windowStart = o["window_start"]?.jsonPrimitive?.content,
            windowEnd = o["window_end"]?.jsonPrimitive?.content,
            isLate = o["is_late"]?.jsonPrimitive?.content?.toBooleanStrictOrNull() ?: false,
        )
    }
    db.routePointsDao().insertAll(points)
    val callRepo = AppServices.callStatusRepository
    points.forEach { p ->
        val order = orderByNumber[p.orderNumber]
        val callTimeIso = (p.callTimeIso?.takeIf { it.isNotBlank() }
            ?: p.estimatedArrivalIso?.takeIf { it.isNotBlank() }?.let { etaIso ->
                runCatching {
                    Instant.parse(etaIso)
                        .minusSeconds(callAdvanceMinutes.toLong() * 60L)
                        .toString()
                }.getOrElse { startTime }
            }
            ?: startTime)
        val cs = CallStatusEntity(
            orderNumber = p.orderNumber,
            callDate = routeDate,
            callTimeIso = callTimeIso,
            arrivalTimeIso = p.estimatedArrivalIso,
            phone = order?.phone ?: "",
            customerName = order?.customerName,
            status = "pending",
            nextAttemptIso = callTimeIso,
        )
        callRepo.upsertAndSchedule(cs)
    }
}

private fun buildPayload(
    orders: List<OrderEntity>,
    startLat: Double,
    startLon: Double,
    startTimeIso: String,
    serviceTimeMinutes: Int,
): String {
    val ordersJson = orders.joinToString(",") { o ->
        val latJson = if (o.latitude != null) o.latitude.toString() else "null"
        val lonJson = if (o.longitude != null) o.longitude.toString() else "null"

        val windowStartJson =
            if (!o.deliveryTimeStart.isNullOrBlank()) "\"${o.deliveryTimeStart!!.escapeJson()}\"" else "null"
        val windowEndJson =
            if (!o.deliveryTimeEnd.isNullOrBlank()) "\"${o.deliveryTimeEnd!!.escapeJson()}\"" else "null"

        val manualArrivalJson = if (o.manualArrivalTime != null) "\"${o.manualArrivalTime}\"" else "null"

        """{"order_number":"${o.orderNumber}","address":"${o.address.escapeJson()}","lat":$latJson,"lon":$lonJson,"window_start":$windowStartJson,"window_end":$windowEndJson,"phone":"${(o.phone ?: "").escapeJson()}","customer_name":"${(o.customerName ?: "").escapeJson()}","manual_arrival_iso":$manualArrivalJson}"""
    }
    return """{"start_location":{"lat":$startLat,"lon":$startLon},"start_time_iso":"$startTimeIso","settings":{"service_time_minutes":$serviceTimeMinutes},"yandex_api_key":"${BuildConfig.YANDEX_MAPS_API_KEY}","two_gis_api_key":"${BuildConfig.TWO_GIS_API_KEY}","orders":[$ordersJson],"route_matrix":{}}"""
}

private fun String.escapeJson(): String = replace("\\", "\\\\").replace("\"", "\\\"")
