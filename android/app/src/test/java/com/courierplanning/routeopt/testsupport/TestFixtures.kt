package com.courierplanning.routeopt.testsupport

import java.io.File

/**
 * Load text from [android/app/src/test/resources] or classpath (see [ParityMapsAdapterTest] history).
 */
fun loadAppTestResourceText(relativePath: String): String {
    val fromWd = File("src/test/resources", relativePath)
    if (fromWd.isFile) {
        return fromWd.readText(Charsets.UTF_8)
    }
    val loaders = listOfNotNull(
        Thread.currentThread().contextClassLoader,
        TestFixturesMark::class.java.classLoader,
    )
    for (cl in loaders) {
        cl.getResourceAsStream(relativePath)?.use { stream ->
            return stream.bufferedReader(Charsets.UTF_8).use { it.readText() }
        }
    }
    error(
        "Missing test resource $relativePath. Tried ${fromWd.absolutePath} (cwd=${File("").absoluteFile}).",
    )
}

/** Anchor class for classLoader (file has no other types). */
private object TestFixturesMark
