package com.courierplanning.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
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
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Timeline
import com.courierplanning.AppServices
import com.courierplanning.data.db.OrderEntity
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.time.LocalDate
import java.time.format.DateTimeFormatter

@Composable
fun OrdersScreen(
    onOpenRoute: () -> Unit,
    onOpenCalls: () -> Unit,
    onOpenImportText: () -> Unit,
    onOpenSettings: () -> Unit,
) {
    val today = remember { LocalDate.now() }
    val todayIso = remember { today.toString() }
    val formattedDate = remember { today.format(DateTimeFormatter.ofPattern("dd.MM.yyyy")) }
    var orders by remember { mutableStateOf<List<OrderEntity>>(emptyList()) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(todayIso) {
        val list = withContext(Dispatchers.IO) {
            AppServices.db.ordersDao().listByDate(todayIso)
        }
        orders = list
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
    ) {
        Column(
            modifier = Modifier.fillMaxSize(),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = if (orders.isEmpty()) formattedDate else "$formattedDate · ${orders.size} заказов",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    IconButton(onClick = onOpenImportText) {
                        Icon(Icons.Default.Download, contentDescription = "Импорт")
                    }
                    IconButton(onClick = { /* TODO: filter later */ }) {
                        Icon(Icons.Default.Timeline, contentDescription = "Фильтр/сортировка")
                    }
                    IconButton(onClick = {
                        scope.launch(Dispatchers.IO) {
                            val list = AppServices.db.ordersDao().listByDate(todayIso)
                            withContext(Dispatchers.Main) { orders = list }
                        }
                    }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Обновить")
                    }
                    IconButton(onClick = onOpenSettings) {
                        Icon(Icons.Default.Settings, contentDescription = "Настройки")
                    }
                }
            }

            if (orders.isEmpty()) {
                Spacer(Modifier.height(16.dp))
                Text(
                    text = "Нет заказов на сегодня.\nИмпортируйте из текста или добавьте тестовый заказ.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            } else {
                LazyColumn(
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    items(orders, key = { it.id }) { o ->
                        OrderCard(order = o)
                    }
                }
            }
        }

        FloatingActionButton(
            onClick = {
                scope.launch(Dispatchers.IO) {
                    val testOrder = OrderEntity(
                        orderDate = todayIso,
                        orderNumber = "TEST-${System.currentTimeMillis() % 10000}",
                        address = "Тестовая ул. 1",
                        deliveryTimeStart = "10:00",
                        deliveryTimeEnd = "13:00",
                        phone = "+79001234567",
                        customerName = "Тест",
                    )
                    AppServices.db.ordersDao().upsert(testOrder)
                    val list = AppServices.db.ordersDao().listByDate(todayIso)
                    withContext(Dispatchers.Main) { orders = list }
                }
            },
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .padding(16.dp),
        ) {
            Icon(Icons.Default.Add, contentDescription = "Добавить заказ")
        }
    }
}

@Composable
private fun OrderCard(order: OrderEntity) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant,
        ),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(
                    text = "№${order.orderNumber}",
                    style = MaterialTheme.typography.bodyMedium,
                )
                Text(
                    text = "${order.deliveryTimeStart ?: "?"}–${order.deliveryTimeEnd ?: "?"}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Text(
                text = order.address,
                style = MaterialTheme.typography.bodyMedium,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            val info = buildString {
                if (!order.customerName.isNullOrBlank()) append(order.customerName)
                if (!order.phone.isNullOrBlank()) {
                    if (isNotEmpty()) append(" • ")
                    append(order.phone)
                }
            }
            if (info.isNotEmpty()) {
                Text(
                    text = info,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 12.sp,
                )
            }
        }
    }
}


