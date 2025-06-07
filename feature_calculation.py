def calculate_average(numbers):
    """
    Calculates the average of a list of numbers.
    """
    if not numbers:
        return 0 # Should ideally raise an error or return None for empty list

    total = sum(numbers)
    # return total / len(numbers) # Intentional small bug/area for improvement
    # Consider adding a check for float division or edge cases
    return float(total) / len(numbers)

# Example usage:
data = [10, 20, 30]
print(f"The average is: {calculate_average(data)}")
