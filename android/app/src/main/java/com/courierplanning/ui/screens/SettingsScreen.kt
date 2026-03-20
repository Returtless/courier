package com.courierplanning.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.courierplanning.AppServices
import com.courierplanning.data.db.SettingsEntity
import com.courierplanning.settings.StartLocationPrefs
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@Composable
fun SettingsScreen(
    onBack: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var serviceTimeText by remember { mutableStateOf("10") }
    var startTimeText by remember { mutableStateOf("09:00") }
    var startLatText by remember { mutableStateOf("59.93") }
    var startLonText by remember { mutableStateOf("30.31") }
    var isLoaded by remember { mutableStateOf(false) }
    val context = LocalContext.current

    LaunchedEffect(Unit) {
        val current = withContext(Dispatchers.IO) {
            AppServices.db.settingsDao().get() ?: SettingsEntity()
        }
        serviceTimeText = current.serviceTimeMinutes.toString()
        val startCfg = StartLocationPrefs.load(context)
        startTimeText = startCfg.startTimeLocal
        startLatText = startCfg.startLat.toString()
        startLonText = startCfg.startLon.toString()
        isLoaded = true
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            text = "Параметры маршрута и старта",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        OutlinedTextField(
            value = serviceTimeText,
            onValueChange = { new ->
                // Разрешаем только цифры и пустую строку
                if (new.all { it.isDigit() } || new.isEmpty()) {
                    serviceTimeText = new
                }
            },
            label = { Text("Время на точке, минут") },
            singleLine = true,
        )

        OutlinedTextField(
            value = startTimeText,
            onValueChange = { new ->
                // Разрешаем только цифры, двоеточие и пустую строку
                if (new.all { it.isDigit() || it == ':' } || new.isEmpty()) {
                    startTimeText = new
                }
            },
            label = { Text("Время старта маршрута (HH:MM)") },
            singleLine = true,
        )

        Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
            OutlinedTextField(
                value = startLatText,
                onValueChange = { startLatText = it },
                label = { Text("Стартовая широта") },
                singleLine = true,
                modifier = Modifier.weight(1f),
            )
            androidx.compose.foundation.layout.Spacer(modifier = Modifier.padding(4.dp))
            OutlinedTextField(
                value = startLonText,
                onValueChange = { startLonText = it },
                label = { Text("Стартовая долгота") },
                singleLine = true,
                modifier = Modifier.weight(1f),
            )
        }

        OutlinedButton(
            onClick = {
                scope.launch(Dispatchers.IO) {
                    val minutes = serviceTimeText.toIntOrNull()?.coerceIn(1, 60) ?: 10
                    val current = AppServices.db.settingsDao().get() ?: SettingsEntity()
                    val updated = current.copy(serviceTimeMinutes = minutes)
                    AppServices.db.settingsDao().upsert(updated)
                    // Сохраняем стартовую точку и время в SharedPreferences
                    val lat = startLatText.toDoubleOrNull() ?: 59.93
                    val lon = startLonText.toDoubleOrNull() ?: 30.31
                    val time = startTimeText.ifBlank { "09:00" }
                    StartLocationPrefs.save(
                        context,
                        StartLocationPrefs.load(context).copy(
                            startLat = lat,
                            startLon = lon,
                            startTimeLocal = time,
                        ),
                    )
                    withContext(Dispatchers.Main) {
                        serviceTimeText = minutes.toString()
                        onBack()
                    }
                }
            },
            enabled = isLoaded && serviceTimeText.toIntOrNull() != null,
            shape = RoundedCornerShape(12.dp),
        ) {
            Text("Сохранить")
        }

        Text("Эти настройки используются при построении маршрута: время на точке, время и координаты старта.")
    }
}

