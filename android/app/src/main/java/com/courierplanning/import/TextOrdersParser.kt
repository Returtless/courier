package com.courierplanning.import

data class ParsedOrder(
    val orderNumber: String,
    val address: String,
    val customerName: String? = null,
    val phone: String? = null,
    val deliveryTimeStart: String? = null, // HH:mm
    val deliveryTimeEnd: String? = null,   // HH:mm
    val comment: String? = null,
    val rawBlock: String,
)

data class ParseIssue(
    val message: String,
    val blockPreview: String,
)

data class ParseResult(
    val orders: List<ParsedOrder>,
    val issues: List<ParseIssue>,
)

object TextOrdersParser {
    private val orderNumberRegexes = listOf(
        Regex("""Заказ\s*№?\s*(\d+)""", setOf(RegexOption.IGNORE_CASE)),
        Regex("""Order\s*№?\s*(\d+)""", setOf(RegexOption.IGNORE_CASE)),
        Regex("""№\s*(\d{6,})""", setOf(RegexOption.IGNORE_CASE)),
    )

    private val addressRegexes = listOf(
        Regex(
            """Адрес\s+доставки:?\s*(.+?)(?=\n\s*(Покупатель:|Buyer:|Имя:|Телефон:|Phone:)|$)""",
            setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL),
        ),
        Regex(
            """Delivery\s+address:?\s*(.+?)(?=\n\s*(Покупатель:|Buyer:|Имя:|Телефон:|Phone:)|$)""",
            setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL),
        ),
        Regex(
            """Адрес:?\s*(.+?)(?=\n\s*(Покупатель:|Buyer:)|$)""",
            setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL),
        ),
    )

    private val nameRegexes = listOf(
        Regex("""Имя:?\s*([А-Яа-яЁёA-Za-z]+)""", setOf(RegexOption.IGNORE_CASE)),
        Regex("""Name:?\s*([А-Яа-яЁёA-Za-z]+)""", setOf(RegexOption.IGNORE_CASE)),
        Regex("""Покупатель:.*?Имя:?\s*([А-Яа-яЁёA-Za-z]+)""", setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL)),
    )

    private val phoneRegexes = listOf(
        Regex("""Телефон:?\s*(\+?7\d{10})""", setOf(RegexOption.IGNORE_CASE)),
        Regex("""Phone:?\s*(\+?7\d{10})""", setOf(RegexOption.IGNORE_CASE)),
        Regex("""(\+7\d{10})"""),
        Regex("""(8\d{10})"""),
        Regex("""(\+?\d[\d\s\-\(\)]{9,})"""),
    )

    private val timeWindowRegexes = listOf(
        Regex("""(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})"""),
        Regex("""\((\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})\)"""),
        Regex("""(\d{1,2}:\d{2})\s*—\s*(\d{1,2}:\d{2})"""),
    )

    fun parse(text: String): ParseResult {
        val trimmed = text.trim()
        if (trimmed.isEmpty()) return ParseResult(emptyList(), emptyList())

        // 1. Пробуем парсинг как в bot.parse_line:
        //  - расширенный формат с '|'
        //  - "Время Номер Адрес"
        //  - "Номер Адрес" / "Номер ... "
        val lineResult = parseLineBasedFormat(trimmed)
        if (lineResult.orders.isNotEmpty() || lineResult.issues.isNotEmpty()) {
            return lineResult
        }

        // 2. Fallback: старый формат как в ImageOrderParser._parse_text (один большой блок)
        val orders = mutableListOf<ParsedOrder>()
        val issues = mutableListOf<ParseIssue>()

        val parsed = parseSingleBlock(trimmed)
        if (parsed != null) {
            orders += parsed
        } else {
            issues += ParseIssue(
                message = "Не удалось извлечь обязательные поля (номер заказа и адрес).",
                blockPreview = trimmed.take(220),
            )
        }

        return ParseResult(orders = orders, issues = issues)
    }

    private fun parseLineBasedFormat(text: String): ParseResult {
        val orders = mutableListOf<ParsedOrder>()
        val issues = mutableListOf<ParseIssue>()

        val lines = text.lines()
        for (line in lines) {
            val trimmedLine = line.trim()
            if (trimmedLine.isEmpty()) continue

            try {
                val order = parseSingleLine(trimmedLine)
                orders += order
            } catch (e: IllegalArgumentException) {
                issues += ParseIssue(
                    message = e.message ?: "Ошибка парсинга строки",
                    blockPreview = trimmedLine.take(220),
                )
            }
        }

        // Если ни одна строка не подошла под паттерн — считаем, что этот формат не наш, вернём пустой результат,
        // чтобы сработал fallback.
        if (orders.isEmpty() && issues.isEmpty()) {
            return ParseResult(emptyList(), emptyList())
        }

        return ParseResult(orders = orders, issues = issues)
    }

    private fun parseSingleLine(line: String): ParsedOrder {
        val trimmed = line.trim()
        if (trimmed.isEmpty()) throw IllegalArgumentException("Пустая строка")

        // === 1. Расширенный формат с '|' ===
        if ('|' in trimmed) {
            val parts = trimmed.split('|').map { it.trim() }
            if (parts.size < 3) {
                throw IllegalArgumentException("Недостаточно данных в расширенном формате. Формат: Имя|Телефон|Адрес|Комментарий")
            }

            var orderNumber: String? = null
            var customerName: String? = null
            var phone: String? = null
            var address: String? = null
            var comment: String? = null

            val firstPart = parts[0]
            val isFirstOrderNumber = firstPart.matches(Regex("""^\d{6,}$"""))

            if (isFirstOrderNumber) {
                // Номер заказа в начале: Номер|Имя|Телефон|Адрес|Комментарий
                orderNumber = firstPart
                if (parts.size >= 2) customerName = parts[1].ifBlank { null }
                if (parts.size >= 3) phone = parts[2].ifBlank { null }
                if (parts.size >= 4) address = parts[3].ifBlank { null }
                if (parts.size >= 5) comment = parts[4].ifBlank { null }
            } else {
                // Обычный формат: Имя|Телефон|Адрес|Комментарий
                customerName = firstPart.ifBlank { null }
                if (parts.size >= 2) phone = parts[1].ifBlank { null }
                if (parts.size >= 3) address = parts[2].ifBlank { null }
                if (parts.size >= 4) comment = parts[3].ifBlank { null }
                // Проверяем последнюю часть на номер заказа
                val lastPart = parts.last().trim()
                if (lastPart.matches(Regex("""^\d{6,}$"""))) {
                    orderNumber = lastPart
                    // Если есть пятая часть, она считается комментарием
                    if (parts.size > 4) {
                        comment = parts[3].ifBlank { null }
                    }
                }
            }

            if (orderNumber.isNullOrBlank()) {
                throw IllegalArgumentException("Номер заказа обязателен. Укажите его в начале или конце: НомерЗаказа|Имя|Телефон|Адрес или Имя|Телефон|Адрес|НомерЗаказа")
            }

            val finalAddress = address ?: ""
            return ParsedOrder(
                orderNumber = orderNumber,
                address = finalAddress,
                customerName = customerName,
                phone = phone,
                comment = comment,
                rawBlock = line,
            )
        }

        // === 2. Формат: Время Номер Адрес ===
        val timePattern = Regex("""(\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2})""")
        val timeMatch = timePattern.find(trimmed)

        var orderNumber: String
        var address: String? = null
        var timeStart: String? = null
        var timeEnd: String? = null

        if (timeMatch != null) {
            val timeWindow = timeMatch.groupValues[1].trim()
            val remainingText = trimmed.replace(timeWindow, "").trim()

            // Разбираем окно на начало и конец
            val parts = timeWindow.split('-')
            if (parts.size == 2) {
                timeStart = parts[0].trim()
                timeEnd = parts[1].trim()
            }

            val orderNumMatch = Regex("""^(\d{6,})\s*(.*)$""").find(remainingText)
            if (orderNumMatch != null) {
                orderNumber = orderNumMatch.groupValues[1]
                address = orderNumMatch.groupValues[2].trim().ifBlank { null }
            } else {
                val anyOrderMatch = Regex("""\b(\d{6,})\b""").find(remainingText)
                if (anyOrderMatch != null) {
                    orderNumber = anyOrderMatch.groupValues[1]
                    address = remainingText.replace(orderNumber, "").trim().ifBlank { null }
                } else {
                    throw IllegalArgumentException("Не найден номер заказа (должно быть минимум 6 цифр)")
                }
            }
        } else {
            // === 3. Без времени ===
            val startMatch = Regex("""^(\d{6,})\s+(.+)$""").find(trimmed)
            if (startMatch != null) {
                orderNumber = startMatch.groupValues[1]
                address = startMatch.groupValues[2].trim().ifBlank { null }
            } else {
                val anyOrderMatch = Regex("""\b(\d{6,})\b""").find(trimmed)
                if (anyOrderMatch != null) {
                    orderNumber = anyOrderMatch.groupValues[1]
                    address = trimmed.replace(orderNumber, "").trim().ifBlank { null }
                } else {
                    throw IllegalArgumentException("Не найден номер заказа. Формат: Время НомерЗаказа Адрес")
                }
            }
        }

        if (address != null && address.length < 3) {
            throw IllegalArgumentException("Адрес слишком короткий (минимум 3 символа)")
        }

        val finalAddress = address ?: ""
        return ParsedOrder(
            orderNumber = orderNumber,
            address = finalAddress,
            deliveryTimeStart = timeStart,
            deliveryTimeEnd = timeEnd,
            rawBlock = line,
        )
    }

    private fun parseSingleBlock(block: String): ParsedOrder? {
        val orderNumber = extractFirstGroup(orderNumberRegexes, block)?.trim()
        val address = extractAddress(block)
        if (orderNumber.isNullOrBlank() || address.isNullOrBlank()) return null

        val customerName = extractFirstGroup(nameRegexes, block)?.trim()?.takeIf { it.length >= 2 }
        val phone = extractPhone(block)
        val (twStart, twEnd) = extractTimeWindow(block)
        val comment = buildString {
            if (Regex("""бесконтактная""", RegexOption.IGNORE_CASE).containsMatchIn(block)) {
                append("Бесконтактная доставка")
            }
        }.takeIf { it.isNotBlank() }

        return ParsedOrder(
            orderNumber = orderNumber,
            address = address,
            customerName = customerName,
            phone = phone,
            deliveryTimeStart = twStart,
            deliveryTimeEnd = twEnd,
            comment = comment,
            rawBlock = block,
        )
    }

    private fun extractAddress(block: String): String? {
        val match = addressRegexes.firstNotNullOfOrNull { it.find(block) } ?: return null
        val raw = match.groupValues[1]
        val cleanedLines = raw.lines()
            .map { it.trim() }
            .filter { it.isNotEmpty() }
            .filterNot { it.equals("Бесконтактная", ignoreCase = true) || it.equals("! Бесконтактная", ignoreCase = true) }
            .map { it.replace(Regex("""\s+"""), " ") }

        val joined = cleanedLines.joinToString(" ").trim()
        return joined.takeIf { it.length >= 10 }
    }

    private fun extractPhone(block: String): String? {
        val raw = extractFirstGroup(phoneRegexes, block) ?: return null
        val compact = raw.replace(Regex("""[\s\-\(\)]"""), "")
        if (compact.length < 10) return null

        val normalized = when {
            compact.startsWith("+") -> compact
            compact.startsWith("8") && compact.length >= 11 -> "+7" + compact.drop(1)
            compact.startsWith("7") && compact.length >= 11 -> "+$compact"
            else -> compact
        }

        return normalized.takeIf { it.length >= 11 }
    }

    private fun extractTimeWindow(block: String): Pair<String?, String?> {
        for (rx in timeWindowRegexes) {
            val m = rx.find(block) ?: continue
            val start = m.groupValues.getOrNull(1)?.trim()
            val end = m.groupValues.getOrNull(2)?.trim()
            if (!start.isNullOrBlank() && !end.isNullOrBlank()) return start to end
        }
        return null to null
    }

    private fun extractFirstGroup(regexes: List<Regex>, text: String): String? {
        for (rx in regexes) {
            val m = rx.find(text) ?: continue
            if (m.groupValues.size >= 2) return m.groupValues[1]
        }
        return null
    }
}

