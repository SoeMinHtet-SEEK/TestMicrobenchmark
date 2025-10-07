package com.example.benchmark

class UserMapper {
        fun mapToUiModel(dto: UserDto): UserUiModel {
            return UserUiModel(
                id = dto.id,
                fullName = "${dto.firstName} ${dto.lastName}",
                displayEmail = dto.email.lowercase(),
                ageGroup = when {
                    dto.age < 18 -> "Youth"
                    dto.age < 35 -> "Young Adult"
                    dto.age < 50 -> "Adult"
                    else -> "Senior"
                },
                fullAddress = buildFullAddress(dto.address),
                primaryPhone = dto.phoneNumbers.firstOrNull(),
                status = if (dto.isActive) "Active" else "Inactive",
                memberSince = formatDate(dto.registrationDate),
                badgeCount = dto.tags.size
            )
        }

        fun mapToUiModelList(dtos: List<UserDto>): List<UserUiModel> {
            return dtos.map { mapToUiModel(it) }
        }

        private fun buildFullAddress(address: AddressDto): String {
            return "${address.street}, ${address.city}, ${address.state} ${address.zipCode}, ${address.country}"
        }

        private fun formatDate(timestamp: Long): String {
            val year = 2020 + (timestamp % 5).toInt()
            return "Member since $year"
        }
    }