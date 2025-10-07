plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.benchmark)
    alias(libs.plugins.kotlin.android)
}

android {
    namespace = "com.example.benchmark"
    compileSdk = 36

    defaultConfig {
        minSdk = 26
        targetSdk = 36
        testInstrumentationRunner = "androidx.benchmark.junit4.AndroidBenchmarkRunner"

        // Emulator-friendly settings
        testInstrumentationRunnerArguments["androidx.benchmark.suppressErrors"] = "EMULATOR,LOW-BATTERY,INSUFFICIENT-STORAGE"
        testInstrumentationRunnerArguments["androidx.benchmark.output.enable"] = "true"
        testInstrumentationRunnerArguments["androidx.benchmark.dryRunMode.enable"] = "false"
    }

    testBuildType = "release"

    buildTypes {
        debug {
            isMinifyEnabled = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "benchmark-proguard-rules.pro"
            )
        }
        release {
            isDefault = true
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }

    kotlinOptions {
        jvmTarget = "1.8"
    }
}

dependencies {
    androidTestImplementation(libs.androidx.runner)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.junit)
    androidTestImplementation(libs.androidx.benchmark.junit4)
}

tasks.register("generateBenchmarkReport") {
    group = "verification"
    description = "Generates JSON report for GitHub Actions and Grafana"

    doLast {
        val benchmarkResultsDir = layout.buildDirectory.dir("outputs/connected_android_test_additional_output")
        val outputFile = rootProject.file("benchmark-results.json")

        println("🔍 Looking for benchmark results in: ${benchmarkResultsDir.get().asFile.absolutePath}")

        if (!benchmarkResultsDir.get().asFile.exists()) {
            println("❌ No benchmark results directory found")
            outputFile.writeText("""{"timestamp":"${System.currentTimeMillis()}","gitCommit":"unknown","brand":"generic","device":"emulator","benchmarks":[]}""")
            return@doLast
        }

        // Get metadata from environment
        val timestamp = System.currentTimeMillis()
        val gitCommit = System.getenv("GITHUB_SHA")?.take(7) ?: "unknown"
        val device = System.getenv("DEVICE_MODEL") ?: "emulator"
        val brand = System.getenv("DEVICE_BRAND") ?: "generic"

        val benchmarkResults = mutableListOf<Map<String, Any>>()
        var filesProcessed = 0

        // Walk through ALL subdirectories to find JSON files
        benchmarkResultsDir.get().asFile.walkTopDown().forEach { file ->
            if (file.isFile && file.extension == "json" && file.name.contains("benchmarkData")) {
                println("📄 Processing: ${file.absolutePath}")
                filesProcessed++

                try {
                    val content = file.readText()
                    println("📝 File size: ${content.length} characters")

                    // Find each benchmark block - look for the pattern more carefully
                    var searchIndex = 0
                    while (true) {
                        // Find next benchmark object
                        val benchmarkStart = content.indexOf(""""name"""", searchIndex)
                        if (benchmarkStart == -1) break

                        // Extract test name
                        val nameMatch = """"name"\s*:\s*"([^"]+)"""".toRegex().find(content, benchmarkStart)
                        val className = """"className"\s*:\s*"([^"]+)"""".toRegex().find(content, benchmarkStart)
                        val iterations = """"repeatIterations"\s*:\s*(\d+)""".toRegex().find(content, benchmarkStart)

                        if (nameMatch != null && className != null) {
                            val testName = nameMatch.groupValues[1]
                            val classNameValue = className.groupValues[1]
                            val iterationsValue = iterations?.groupValues?.get(1)?.toIntOrNull() ?: 100

                            println("  📌 Found test: $classNameValue.$testName")

                            // Find timeNs metrics block for this benchmark
                            val timeNsStart = content.indexOf(""""timeNs"""", benchmarkStart)
                            if (timeNsStart != -1 && timeNsStart < benchmarkStart + 5000) { // within reasonable range
                                val timeSection = content.substring(timeNsStart, minOf(timeNsStart + 1000, content.length))

                                val minTime = """"minimum"\s*:\s*([\d.E+-]+)""".toRegex().find(timeSection)?.groupValues?.get(1)?.toDouble() ?: 0.0
                                val maxTime = """"maximum"\s*:\s*([\d.E+-]+)""".toRegex().find(timeSection)?.groupValues?.get(1)?.toDouble() ?: 0.0
                                val medianTime = """"median"\s*:\s*([\d.E+-]+)""".toRegex().find(timeSection)?.groupValues?.get(1)?.toDouble() ?: 0.0

                                println("    ⏱️  Time: min=$minTime, median=$medianTime, max=$maxTime")

                                // Find allocationCount metrics - search from benchmarkStart, not timeNsStart
                                // because allocationCount is a sibling of timeNs in the metrics object
                                val allocStart = content.indexOf(""""allocationCount"""", benchmarkStart)
                                var minAlloc = 0.0
                                var maxAlloc = 0.0
                                var medianAlloc = 0.0

                                // Make sure we find allocationCount within the same benchmark block (not the next one)
                                if (allocStart != -1 && allocStart < benchmarkStart + 10000) {
                                    val allocSection = content.substring(allocStart, minOf(allocStart + 1000, content.length))
                                    minAlloc = """"minimum"\s*:\s*([\d.E+-]+)""".toRegex().find(allocSection)?.groupValues?.get(1)?.toDouble() ?: 0.0
                                    maxAlloc = """"maximum"\s*:\s*([\d.E+-]+)""".toRegex().find(allocSection)?.groupValues?.get(1)?.toDouble() ?: 0.0
                                    medianAlloc = """"median"\s*:\s*([\d.E+-]+)""".toRegex().find(allocSection)?.groupValues?.get(1)?.toDouble() ?: 0.0

                                    println("    💾 Allocations: min=$minAlloc, median=$medianAlloc, max=$maxAlloc")
                                } else {
                                    println("    ⚠️  No allocation data found for this test")
                                }

                                // Create result entry
                                val fullTestName = "$classNameValue.$testName"
                                val result = mapOf(
                                    "testName" to fullTestName,
                                    "minTimeNs" to minTime.toLong(),
                                    "medianTimeNs" to medianTime.toLong(),
                                    "maxTimeNs" to maxTime.toLong(),
                                    "minAllocationCount" to minAlloc.toLong(),
                                    "medianAllocationCount" to medianAlloc.toLong(),
                                    "maxAllocationCount" to maxAlloc.toLong(),
                                    "iterations" to iterationsValue
                                )

                                benchmarkResults.add(result)
                                println("    ✅ Added benchmark result")
                            }
                        }

                        // Move search forward
                        searchIndex = benchmarkStart + 100
                        if (searchIndex >= content.length) break
                    }

                } catch (e: Exception) {
                    println("⚠️ Error processing ${file.name}: ${e.message}")
                    e.printStackTrace()
                }
            }
        }

        // Generate JSON output
        val jsonOutput = buildString {
            append("""{"timestamp":"$timestamp",""")
            append(""""gitCommit":"$gitCommit",""")
            append(""""brand":"$brand",""")
            append(""""device":"$device",""")
            append(""""benchmarks":[""")

            benchmarkResults.forEachIndexed { index, result ->
                if (index > 0) append(",")
                append("""{""")
                append(""""testName":"${result["testName"]}",""")
                append(""""minTimeNs":${result["minTimeNs"]},""")
                append(""""medianTimeNs":${result["medianTimeNs"]},""")
                append(""""maxTimeNs":${result["maxTimeNs"]},""")
                append(""""minAllocationCount":${result["minAllocationCount"]},""")
                append(""""medianAllocationCount":${result["medianAllocationCount"]},""")
                append(""""maxAllocationCount":${result["maxAllocationCount"]},""")
                append(""""iterations":${result["iterations"]}""")
                append("""}""")
            }

            append("]}")
        }

        outputFile.writeText(jsonOutput)
        println("📊 Generated report with ${benchmarkResults.size} benchmarks from $filesProcessed files")
        println("📊 Output: $jsonOutput")
    }
}