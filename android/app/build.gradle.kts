import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.ksp)
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

android {
    namespace = "com.courierplanning"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.courierplanning"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0"

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

