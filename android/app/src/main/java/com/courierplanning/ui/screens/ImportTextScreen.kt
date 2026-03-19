package com.courierplanning.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.courierplanning.AppServices
import com.courierplanning.data.db.OrderEntity
import com.courierplanning.import.TextOrdersParser
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.time.LocalDate

@Composable
fun ImportTextScreen(
    onBack: () -> Unit,
    onDone: () -> Unit,
) {
    val today = remember { LocalDate.now().toString() }
    val scope = rememberCoroutineScope()

    var input by remember { mutableStateOf("") }
    var parseSummary by remember { mutableStateOf<String?>(null) }
    var previewText by remember { mutableStateOf<String?>(null) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
            .verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Импорт заказов (текст) на $today")

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(
                onClick = {
                    input = SAMPLE_TEXT
                    parseSummary = null
                    previewText = null
                },
                shape = RoundedCornerShape(12.dp),
            ) { Text("Вставить пример") }
        }

        OutlinedTextField(
            value = input,
            onValueChange = { input = it },
            label = { Text("Вставьте текст заказа/заказов") },
            modifier = Modifier.fillMaxWidth(),
            minLines = 8,
        )

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(
                onClick = {
                    val result = TextOrdersParser.parse(input)
                    parseSummary = "Найдено заказов: ${result.orders.size}, проблемных блоков: ${result.issues.size}"
                    previewText = buildString {
                        if (result.orders.isNotEmpty()) {
                            appendLine("Превью:")
                            result.orders.take(10).forEach { o ->
                                appendLine("• №${o.orderNumber} · ${o.address}")
                                appendLine("  ${o.deliveryTimeStart ?: "?"}–${o.deliveryTimeEnd ?: "?"} · ${o.phone ?: "без телефона"} · ${o.customerName ?: "без имени"}")
                            }
                            if (result.orders.size > 10) appendLine("… и ещё ${result.orders.size - 10}")
                            appendLine()
                        }
                        if (result.issues.isNotEmpty()) {
                            appendLine("Проблемные блоки (первые 3):")
                            result.issues.take(3).forEachIndexed { idx, it ->
                                appendLine("${idx + 1}) ${it.message}")
                                appendLine(it.blockPreview)
                                appendLine()
                            }
                        }
                    }.trim().ifEmpty { null }
                },
                shape = RoundedCornerShape(12.dp),
            ) { Text("Проверить") }

            OutlinedButton(
                onClick = {
                    scope.launch(Dispatchers.IO) {
                        val result = TextOrdersParser.parse(input)
                        val dao = AppServices.db.ordersDao()
                        var imported = 0
                        for (o in result.orders) {
                            val entity = OrderEntity(
                                orderDate = today,
                                orderNumber = o.orderNumber,
                                address = o.address,
                                deliveryTimeStart = o.deliveryTimeStart,
                                deliveryTimeEnd = o.deliveryTimeEnd,
                                phone = o.phone,
                                customerName = o.customerName,
                                comment = o.comment,
                                rawOcrText = o.rawBlock,
                            )
                            dao.upsert(entity)
                            imported += 1
                        }
                        withContext(Dispatchers.Main) {
                            parseSummary = "Импортировано в базу: $imported (распознано заказов: ${result.orders.size}), проблемных блоков: ${result.issues.size}"
                            previewText = buildString {
                                if (result.orders.isNotEmpty()) {
                                    appendLine("Импортированные заказы (макс 10):")
                                    result.orders.take(10).forEach { o ->
                                        appendLine("• №${o.orderNumber} · ${o.address}")
                                        appendLine("  ${o.deliveryTimeStart ?: "?"}–${o.deliveryTimeEnd ?: "?"} · ${o.phone ?: "без телефона"} · ${o.customerName ?: "без имени"}")
                                    }
                                    if (result.orders.size > 10) appendLine("… и ещё ${result.orders.size - 10}")
                                }
                                if (result.issues.isNotEmpty()) {
                                    appendLine()
                                    appendLine("Проблемные блоки при импорте (первые 3):")
                                    result.issues.take(3).forEachIndexed { idx, it ->
                                        appendLine("${idx + 1}) ${it.message}")
                                        appendLine(it.blockPreview)
                                        appendLine()
                                    }
                                }
                            }.trim().ifEmpty { null }
                        }
                    }
                },
                enabled = input.isNotBlank(),
                shape = RoundedCornerShape(12.dp),
            ) { Text("Импортировать") }
        }

        parseSummary?.let { Text(it) }
        previewText?.let { Text(it) }
    }
}

private const val SAMPLE_TEXT = """
Заказ № 3269184
Адрес доставки:
г. Москва, Тестовая ул., д. 1, кв. 12
Покупатель:
Имя: Иван
Телефон: +79001234567
(10:00-13:00)
"""

