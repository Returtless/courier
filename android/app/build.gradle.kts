import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.ksp)
    alias(libs.plugins.chaquopy)
}

fun escapeBuildConfigString(s: String): String =
    s.replace("\\", "\\\\").replace("\"", "\\\"")

val localProperties = Properties().apply {
    val localPropertiesFile = rootProject.file("local.properties")
    if (localPropertiesFile.exists()) {
        localPropertiesFile.inputStream().use { load(it) }
    }
}

fun propOrEnv(name: String): String {
    val fromGradle = findProperty(name) as? String
    if (fromGradle != null) return fromGradle
    val fromLocal = localProperties.getProperty(name)
    if (fromLocal != null) return fromLocal
    return System.getenv(name) ?: ""
}

val yandexApiKeyValue = propOrEnv("YANDEX_MAPS_API_KEY")
val twoGisApiKeyValue = propOrEnv("TWO_GIS_API_KEY")

// Chaquopy ставит Python-зависимости отдельно на КАЖДЫЙ ABI → 3 ABI ≈ в 3 раза дольше pip.
// Включение: android/gradle.properties → courier.fastAbi=true
// Или в PowerShell (обязательно -P и кавычки): gradlew installDebug "-Pcourier.fastAbi=true"
val courierFastAbi: Boolean =
    when (val p = findProperty("courier.fastAbi")) {
        is Boolean -> p
        is String -> p.equals("true", ignoreCase = true)
        else -> false
    } || System.getenv("COURIER_FAST_ABI") == "1"

android {
    namespace = "com.courierplanning"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.courierplanning"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0"

        // Required by Chaquopy. Меньше ABI → быстрее :generateDebugPythonRequirements.
        ndk {
            abiFilters += if (courierFastAbi) {
                listOf("arm64-v8a")
            } else {
                listOf("arm64-v8a", "armeabi-v7a", "x86_64")
            }
        }

        buildConfigField(
            "String",
            "YANDEX_MAPS_API_KEY",
            "\"${escapeBuildConfigString(yandexApiKeyValue)}\"",
        )
        buildConfigField(
            "String",
            "TWO_GIS_API_KEY",
            "\"${escapeBuildConfigString(twoGisApiKeyValue)}\"",
        )
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
        debug {
            isMinifyEnabled = false
        }
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    // Ensure consistent JVM target for Java/Kotlin/KSP.
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    packaging {
        resources {
            excludes += setOf(
                "META-INF/AL2.0",
                "META-INF/LGPL2.1",
            )
        }
    }

    // Local unit tests: ensure src/test/resources is on the classpath (parity JSON fixtures).
    sourceSets {
        getByName("test") {
            resources.srcDir("src/test/resources")
        }
    }
}

// Kotlin toolchain and bytecode target (affects KSP too).
kotlin {
    jvmToolchain(17)
}

chaquopy {
    defaultConfig {
        // Keep Python requirements minimal; we reuse project code.
        // If later needed, add pip { install("...") } here.
        pyc {
            // Disable bytecode compilation for now to avoid buildPython version mismatch
            // (Chaquopy's pyc task targets a specific Python bytecode version).
            // We can re-enable later by pinning buildPython to the exact version Chaquopy expects.
            src = false
        }

        pip {
            // Use a minimal-but-complete set for src/services/maps_service.py + route_optimizer.py
            // Keep versions unpinned to avoid "no matching distribution" from Chaquopy's mirror.
            install("requests")
            install("numpy")
            // ortools нет для Android в Chaquopy; на устройстве используется GeneticRouteOptimizer (как в боте).
            install("sqlalchemy")
            // Pydantic 2 тянет pydantic-core (Rust) — на Chaquopy нет колеса, сборка с sdist падает.
            // На Android достаточно Pydantic 1.x (pure Python); код в src/ совместим с v1 и v2.
            install("pydantic>=1.10.13,<2")
            // Not required for current Chaquopy optimizer path:
            // - maps_service uses sync routing/geocoding via requests (aiohttp optional)
            // - geopy is used only as fallback when no API keys are present

            // Chaquopy already adds its wheel index; keep pip on PyPI + that index (do not pass
            // --index-url, or pure-Python packages like `requests` won't resolve).
            // Put pre-downloaded Android wheels (e.g. NumPy) in `app/chaquopy-local-wheels/`.
            options(
                "--find-links",
                file("chaquopy-local-wheels").absolutePath,
                "--timeout", "1800",
                "--retries", "20",
            )
        }
    }

    sourceSets {
        getByName("main") {
            // НЕ используйте srcDir("../../") — Gradle хеширует весь репозиторий (.git, venv, build) и на
            // Windows падает mergeDebugPythonSources (MD5 / unreadable inputs). Копируем только Python-пакет src/.
            srcDir(layout.buildDirectory.dir("generated/chaquopyPythonRoot"))
        }
    }
}

// Синхронизация courier/src → build/.../chaquopyPythonRoot/src/ (структура для import src.*)
val courierRepoSrc = rootProject.projectDir.parentFile.resolve("src")
tasks.register<Sync>("syncChaquopyPythonSources") {
    from(courierRepoSrc) {
        exclude("**/__pycache__/**")
        exclude("**/*.pyc")
    }
    into(layout.buildDirectory.dir("generated/chaquopyPythonRoot/src"))
}

tasks.matching {
    it.name.startsWith("merge") && it.name.endsWith("PythonSources")
}.configureEach {
    dependsOn("syncChaquopyPythonSources")
}

// JVM unit tests: stable cwd so `src/test/resources/...` file paths in tests resolve.
tasks.withType<Test>().configureEach {
    workingDir = layout.projectDirectory.asFile
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.navigation.compose)

    implementation(platform(libs.androidx.compose.bom))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    debugImplementation("androidx.compose.ui:ui-tooling")

    implementation(libs.androidx.work.runtime)

    implementation(libs.androidx.room.runtime)
    implementation(libs.androidx.room.ktx)

    ksp(libs.androidx.room.compiler)

    implementation(libs.kotlinx.serialization.json)
    implementation(libs.ktor.client.okhttp)
    implementation(libs.ktor.client.content.negotiation)
    implementation(libs.ktor.serialization.kotlinx.json)

    implementation(libs.mlkit.text.recognition)
    implementation(libs.androidx.security.crypto)

    testImplementation(libs.junit)
    // JVM unit tests use stubbed android.jar; JSONObject from SDK is not mocked — use real JSON lib.
    testImplementation(libs.jsonObject)
}

