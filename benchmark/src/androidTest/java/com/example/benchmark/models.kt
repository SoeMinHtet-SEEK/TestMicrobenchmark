package com.example.benchmark

data class UserDto(
    val id: Int,
    val firstName: String,
    val lastName: String,
    val email: String,
    val age: Int,
    val address: AddressDto,
    val phoneNumbers: List<String>,
    val isActive: Boolean,
    val registrationDate: Long,
    val tags: List<String>
)

data class AddressDto(
    val street: String,
    val city: String,
    val state: String,
    val zipCode: String,
    val country: String
)


data class UserUiModel(
    val id: Int,
    val fullName: String,
    val displayEmail: String,
    val ageGroup: String,
    val fullAddress: String,
    val primaryPhone: String?,
    val status: String,
    val memberSince: String,
    val badgeCount: Int
)