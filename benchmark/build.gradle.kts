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
    description = "Generates JSON report for GitHub Actions"

    doLast {
        val benchmarkResultsDir = layout.buildDirectory.dir("outputs/connected_android_test_additional_output")
        val outputFile = rootProject.file("benchmark-results.json")

        println("🔍 Looking for benchmark results in: ${benchmarkResultsDir.get().asFile.absolutePath}")

        if (!benchmarkResultsDir.get().asFile.exists()) {
            println("❌ No benchmark results directory found")
            outputFile.writeText("[]")
            return@doLast
        }

        val results = mutableListOf<Map<String, Any>>()
        var filesProcessed = 0

        // Walk through ALL subdirectories to find JSON files
        benchmarkResultsDir.get().asFile.walkTopDown().forEach { file ->
            if (file.isFile && file.extension == "json" && file.name.contains("benchmarkData")) {
                println("📄 Processing: ${file.name} at ${file.absolutePath}")
                filesProcessed++

                try {
                    val content = file.readText()
                    println("📄 Content preview: ${content.take(200)}...")

                    // Parse the JSON content
                    val nameRegex = """"name"\s*:\s*"([^"]+)"""".toRegex()
                    val medianRegex = """"median"\s*:\s*([\d.]+)""".toRegex()

                    val nameMatches = nameRegex.findAll(content).toList()
                    val medianMatches = medianRegex.findAll(content).toList()

                    println("🔍 Found ${nameMatches.size} test names and ${medianMatches.size} median values")

                    nameMatches.zip(medianMatches).forEach { (nameMatch, medianMatch) ->
                        val name = nameMatch.groupValues[1]
                        val median = medianMatch.groupValues[1].toDoubleOrNull() ?: 0.0

                        if (median > 0) {
                            results.add(mapOf(
                                "name" to name,
                                "value" to median / 1000.0, // Convert ns to μs
                                "unit" to "μs"
                            ))
                            println("✅ Found: $name = ${median / 1000.0}μs")
                        }
                    }
                } catch (e: Exception) {
                    println("⚠️ Error processing ${file.name}: ${e.message}")
                }
            }
        }

        val jsonOutput = "[" + results.joinToString(",") { result ->
            """{"name":"${result["name"]}","value":${result["value"]},"unit":"${result["unit"]}"}"""
        } + "]"

        outputFile.writeText(jsonOutput)
        println("📊 Generated report with ${results.size} benchmarks from $filesProcessed files")
        println("📊 Report content: $jsonOutput")
    }
}