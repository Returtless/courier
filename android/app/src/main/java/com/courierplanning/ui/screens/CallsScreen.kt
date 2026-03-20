package com.courierplanning.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Divider
import androidx.compose.material3.MaterialTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.courierplanning.AppServices
import com.courierplanning.data.db.SettingsEntity
import kotlinx.coroutines.launch
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter

@Composable
fun CallsScreen(onBack: () -> Unit) {
    val scope = rememberCoroutineScope()
    val today = LocalDate.now()
    val calls by AppServices.callStatusRepository.observeForDate(today).collectAsState(initial = emptyList())
    var selectedFilter by remember { mutableStateOf(0) }

    var retryIntervalMinutes by remember { mutableStateOf(2L) }
    var maxAttempts by remember { mutableStateOf(3) }
    LaunchedEffect(Unit) {
        val s = withContext(Dispatchers.IO) {
            AppServices.db.settingsDao().get() ?: SettingsEntity()
        }
        retryIntervalMinutes = s.callRetryIntervalMinutes.toLong()
        maxAttempts = s.callMaxAttempts
    }

    val segments = listOf("Все", "Ожидают", "Успешно", "Нет ответа")
    val statuses = listOf(null, setOf("pending", "rejected"), setOf("confirmed"), setOf("failed"))

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        val dateLabel = remember { today.format(DateTimeFormatter.ofPattern("dd.MM.yyyy")) }
        Text(
            text = "$dateLabel · ${segments[selectedFilter]}",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        SingleChoiceSegmentedButtonRow {
            segments.forEachIndexed { index, label ->
                SegmentedButton(
                    selected = selectedFilter == index,
                    onClick = { selectedFilter = index },
                    shape = SegmentedButtonDefaults.itemShape(index = index, count = segments.size),
                ) {
                    Text(
                        text = label,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        softWrap = false,
                        style = MaterialTheme.typography.labelSmall,
                    )
                }
            }
        }

        val fmt = DateTimeFormatter.ofPattern("HH:mm")
        val filtered = statuses[selectedFilter]?.let { allowed ->
            calls.filter { it.status in allowed }
        } ?: calls

        if (filtered.isEmpty()) {
            Spacer(Modifier.height(16.dp))
            Text(
                "Нет звонков для выбранного фильтра.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        } else {
            Spacer(Modifier.height(8.dp))
            filtered.forEach { cs ->
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp),
                    elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.surfaceVariant,
                    ),
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(12.dp),
                        verticalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text("№${cs.orderNumber}", modifier = Modifier.weight(1f))
                            val t = Instant.parse(cs.callTimeIso).atZone(ZoneId.systemDefault()).toLocalTime()
                            Text(t.format(fmt))
                        }
                        Text("Тел: ${cs.phone}")
                        Text(
                            "Статус: ${cs.status}, попыток: ${cs.attempts}",
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedButton(
                                onClick = { scope.launch { AppServices.callStatusRepository.markConfirmed(cs.id) } },
                                modifier = Modifier.height(40.dp),
                                shape = RoundedCornerShape(12.dp),
                                contentPadding = PaddingValues(horizontal = 10.dp, vertical = 0.dp),
                            ) {
                                Text(
                                    "Выполнено",
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                    softWrap = false,
                                )
                            }
                            OutlinedButton(
                                onClick = {
                                    scope.launch {
                                        AppServices.callStatusRepository.markRejectedAndRetry(
                                            id = cs.id,
                                            retryAfterMinutes = retryIntervalMinutes,
                                            maxAttempts = maxAttempts,
                                        )
                                    }
                                },
                                modifier = Modifier.height(40.dp),
                                shape = RoundedCornerShape(12.dp),
                                contentPadding = PaddingValues(horizontal = 10.dp, vertical = 0.dp),
                            ) {
                                Text(
                                    "Нет ответа",
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                    softWrap = false,
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

