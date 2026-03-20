package com.courierplanning

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.Phone
import androidx.compose.material.icons.filled.Route
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.CenterAlignedTopAppBar
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.courierplanning.notifications.Notifications
import com.courierplanning.ui.theme.CourierTheme
import com.courierplanning.ui.screens.CallsScreen
import com.courierplanning.ui.screens.ImportTextScreen
import com.courierplanning.ui.screens.OrdersScreen
import com.courierplanning.ui.screens.RouteScreen
import com.courierplanning.ui.screens.SettingsScreen

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        AppServices.init(this)
        Notifications.ensureChannels(this)

        setContent {
            CourierTheme {
                Surface {
                    AppShell(
                        initialScreen = intent?.getStringExtra("screen"),
                        initialCallStatusId = intent?.getLongExtra("callStatusId", -1L) ?: -1L,
                    )
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AppShell(initialScreen: String?, initialCallStatusId: Long) {
    val navController = rememberNavController()
    LaunchedEffect(initialScreen) {
        if (initialScreen == "calls") {
            navController.navigate("calls?callStatusId=$initialCallStatusId") {
                popUpTo("orders") { inclusive = false }
            }
        }
    }

    val items = listOf("orders", "route", "calls", "settings")
    val backStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = backStackEntry?.destination?.route

    val topBarTitle = when (currentRoute) {
        "orders" -> "Заказы"
        "route" -> "Маршрут"
        "calls", "calls?callStatusId={callStatusId}" -> "Звонки"
        "settings" -> "Настройки"
        "import_text" -> "Импорт текста"
        else -> "Курьер"
    }

    val navIcons = mapOf(
        "orders" to Icons.Default.List,
        "route" to Icons.Default.Route,
        "calls" to Icons.Default.Phone,
        "settings" to Icons.Default.Settings,
    )

    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = { Text(topBarTitle, style = MaterialTheme.typography.titleLarge) },
                navigationIcon = {
                    if (currentRoute == "settings" || currentRoute == "import_text") {
                        IconButton(onClick = { navController.popBackStack() }) {
                            Icon(Icons.Default.ArrowBack, contentDescription = "Назад")
                        }
                    }
                },
            )
        },
        bottomBar = {
            NavigationBar {
                items.forEach { route ->
                    val label = when (route) {
                        "orders" -> "Заказы"
                        "route" -> "Маршрут"
                        "calls" -> "Звонки"
                        "settings" -> "Настройки"
                        else -> route
                    }
                    NavigationBarItem(
                        selected = currentRoute == route,
                        onClick = {
                            if (currentRoute != route) {
                                // Если целевая вкладка уже в стеке (например Заказы под Настройками) — возвращаемся к ней
                                val popped = navController.popBackStack(route, inclusive = false)
                                if (!popped) {
                                    navController.navigate(route) {
                                        popUpTo("orders") { saveState = true }
                                        launchSingleTop = true
                                        restoreState = true
                                    }
                                }
                            }
                        },
                        icon = { Icon(navIcons[route] ?: Icons.Default.List, contentDescription = label) },
                        label = { Text(label) },
                    )
                }
            }
        },
    ) { paddingValues ->
        NavHost(
            navController = navController,
            startDestination = "orders",
            modifier = Modifier.padding(paddingValues),
        ) {
            composable("orders") {
                OrdersScreen(
                    onOpenRoute = { navController.navigate("route") },
                    onOpenCalls = { navController.navigate("calls") },
                    onOpenImportText = { navController.navigate("import_text") },
                    onOpenSettings = { navController.navigate("settings") },
                )
            }
            composable("route") { RouteScreen(onBack = { /* bottom nav handles navigation */ }) }
            composable("calls") { CallsScreen(onBack = { /* bottom nav handles navigation */ }) }
            composable("calls?callStatusId={callStatusId}") {
                CallsScreen(onBack = { /* bottom nav handles navigation */ })
            }
            composable("import_text") {
                ImportTextScreen(
                    onBack = { navController.popBackStack() },
                    onDone = { navController.popBackStack() },
                )
            }
            composable("settings") {
                SettingsScreen(
                    onBack = { navController.popBackStack() },
                )
            }
        }
    }
}

