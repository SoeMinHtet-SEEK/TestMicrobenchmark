package com.example.benchmark

import androidx.benchmark.junit4.BenchmarkRule
import androidx.benchmark.junit4.measureRepeated
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class UserBenchmark {

    @get:Rule
    val benchmarkRule = BenchmarkRule()

    private fun createSampleUser(id: Int): UserDto {
        return UserDto(
            id = id,
            firstName = "John",
            lastName = "Doe",
            email = "john.doe$id@example.com",
            age = 25 + (id % 40),
            address = AddressDto(
                street = "$id Main Street",
                city = "Springfield",
                state = "IL",
                zipCode = "62701",
                country = "USA"
            ),
            phoneNumbers = listOf(
                "+1-555-000-${String.format("%04d", id)}",
                "+1-555-100-${String.format("%04d", id)}"
            ),
            isActive = id % 2 == 0,
            registrationDate = System.currentTimeMillis() - (id * 86400000L),
            tags = List(id % 5 + 1) { "tag$it" }
        )
    }

    @Test
    fun mapSingleUser() {
        val mapper = UserMapper()
        val user = createSampleUser(1)

        benchmarkRule.measureRepeated {
            mapper.mapToUiModel(user)
        }
    }

    @Test
    fun mapUserList_100Items() {
        val mapper = UserMapper()
        val users = List(100) { createSampleUser(it) }

        benchmarkRule.measureRepeated {
            mapper.mapToUiModelList(users)
        }
    }
}