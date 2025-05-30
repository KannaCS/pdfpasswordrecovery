import itertools
import string


class PasswordGenerator:
    """
    Class for generating password lists with various criteria
    """
    def __init__(self, min_length=4, max_length=6, 
                 use_lowercase=True, use_uppercase=False, 
                 use_digits=True, use_special=False,
                 no_limit=False):
        """
        Initialize with password generation options
        
        Args:
            min_length (int): Minimum password length
            max_length (int): Maximum password length
            use_lowercase (bool): Include lowercase letters
            use_uppercase (bool): Include uppercase letters
            use_digits (bool): Include digits
            use_special (bool): Include special characters
            no_limit (bool): If True, remove the password count limit
        """
        self.min_length = min_length
        self.max_length = max_length
        self.use_lowercase = use_lowercase
        self.use_uppercase = use_uppercase
        self.use_digits = use_digits
        self.use_special = use_special
        
        # Default maximum is 1 million passwords, unless no_limit is True
        self.MAX_PASSWORDS = float('inf') if no_limit else 1000000
        
    def generate_passwords(self, progress_callback=None, pattern_callback=None):
        """
        Generate list of passwords based on the configured options
        
        Args:
            progress_callback (function): Optional callback function for progress updates
                                        Called as progress_callback(current_count, total_estimated)
            pattern_callback (function): Optional callback function for pattern updates
                                        Called as pattern_callback(current_pattern)
        
        Returns:
            list: List of password strings
        """
        # Create character set based on selected options
        chars = ''
        
        if self.use_lowercase:
            chars += string.ascii_lowercase
        if self.use_uppercase:
            chars += string.ascii_uppercase
        if self.use_digits:
            chars += string.digits
        if self.use_special:
            chars += '!@#$%^&*'
            
        # If no options selected, default to lowercase
        if not chars:
            chars = string.ascii_lowercase
            
        # Calculate total estimated combinations for progress reporting
        total_estimate = self.estimate_count()
        
        # Generate passwords
        passwords = []
        count = 0
        
        # Report initial progress
        if progress_callback:
            progress_callback(0, total_estimate)
        
        # Update progress periodically (not on every password to avoid slowdowns)
        progress_interval = max(1, min(10000, total_estimate // 100))  # Update ~100 times during generation
        
        # For each length in the specified range
        for length in range(self.min_length, self.max_length + 1):
            # Estimate the number of combinations for this length
            combinations_count = len(chars) ** length
            
            # If estimated count is too large, skip generating all combinations
            if combinations_count + count > self.MAX_PASSWORDS:
                # Generate a reasonable subset instead
                if length <= 3:  # For short passwords, generate all combinations
                    if pattern_callback:
                        pattern_callback(f"Length {length} passwords with all chars")
                        
                    for combination in itertools.product(chars, repeat=length):
                        pattern = ''.join(combination)
                        passwords.append(pattern)
                        count += 1
                        
                        # Report progress - check if we should continue
                        if progress_callback and count % progress_interval == 0:
                            if not progress_callback(count, total_estimate):
                                return passwords  # Cancelled
                            
                        # Report current pattern occasionally
                        if pattern_callback and count % (progress_interval * 10) == 0:
                            if not pattern_callback(pattern):
                                return passwords  # Cancelled
                        
                        if count >= self.MAX_PASSWORDS:
                            if progress_callback:
                                progress_callback(count, total_estimate)
                            return passwords
                else:
                    # For longer passwords, generate a smart subset
                    # This includes commonly used patterns:
                    
                    # Common password patterns like all lowercase/uppercase
                    if self.use_lowercase:
                        lowercase_chars = string.ascii_lowercase
                        if pattern_callback:
                            pattern_callback(f"Length {length} lowercase passwords")
                            
                        for combo in itertools.product(lowercase_chars, repeat=length):
                            pattern = ''.join(combo)
                            passwords.append(pattern)
                            count += 1
                            
                            # Report progress
                            if progress_callback and count % progress_interval == 0:
                                if not progress_callback(count, total_estimate):
                                    return passwords  # Cancelled
                                
                            # Report current pattern occasionally
                            if pattern_callback and count % (progress_interval * 10) == 0:
                                if not pattern_callback(pattern):
                                    return passwords  # Cancelled
                            
                            if count >= self.MAX_PASSWORDS:
                                if progress_callback:
                                    progress_callback(count, total_estimate)
                                return passwords
                    
                    # Add some numeric patterns
                    if self.use_digits:
                        digits = string.digits
                        if pattern_callback:
                            pattern_callback(f"Length {length} numeric passwords")
                            
                        for combo in itertools.product(digits, repeat=length):
                            pattern = ''.join(combo)
                            passwords.append(pattern)
                            count += 1
                            
                            # Report progress
                            if progress_callback and count % progress_interval == 0:
                                if not progress_callback(count, total_estimate):
                                    return passwords  # Cancelled
                                
                            # Report current pattern occasionally 
                            if pattern_callback and count % (progress_interval * 10) == 0:
                                if not pattern_callback(pattern):
                                    return passwords  # Cancelled
                            
                            if count >= self.MAX_PASSWORDS:
                                if progress_callback:
                                    progress_callback(count, total_estimate)
                                return passwords
                    
                    # Add some mixed patterns (first half letters, second half numbers)
                    if length >= 4 and self.use_lowercase and self.use_digits:
                        half = length // 2
                        if pattern_callback:
                            pattern_callback(f"Length {length} mixed letter-number passwords")
                            
                        for letter_combo in itertools.product(string.ascii_lowercase, repeat=half):
                            letters = ''.join(letter_combo)
                            for digit_combo in itertools.product(string.digits, repeat=length-half):
                                digits = ''.join(digit_combo)
                                password = letters + digits
                                passwords.append(password)
                                count += 1
                                
                                # Report progress
                                if progress_callback and count % progress_interval == 0:
                                    if not progress_callback(count, total_estimate):
                                        return passwords  # Cancelled
                                    
                                # Report current pattern occasionally
                                if pattern_callback and count % (progress_interval * 10) == 0:
                                    if not pattern_callback(password):
                                        return passwords  # Cancelled
                                
                                if count >= self.MAX_PASSWORDS:
                                    if progress_callback:
                                        progress_callback(count, total_estimate)
                                    return passwords
            else:
                # Generate all combinations for this length
                if pattern_callback:
                    pattern_callback(f"All length {length} combinations")
                    
                for combination in itertools.product(chars, repeat=length):
                    pattern = ''.join(combination)
                    passwords.append(pattern)
                    count += 1
                    
                    # Report progress
                    if progress_callback and count % progress_interval == 0:
                        if not progress_callback(count, total_estimate):
                            return passwords  # Cancelled
                        
                    # Report current pattern occasionally
                    if pattern_callback and count % (progress_interval * 10) == 0:
                        if not pattern_callback(pattern):
                            return passwords  # Cancelled
                    
                    if count >= self.MAX_PASSWORDS:
                        if progress_callback:
                            progress_callback(count, total_estimate)
                        return passwords
        
        # Final progress update
        if progress_callback:
            progress_callback(count, total_estimate)
                        
        return passwords
        
    def estimate_count(self):
        """
        Estimate the number of passwords that would be generated
        
        Returns:
            int: Estimated number of passwords
        """
        # Count available characters
        char_count = 0
        if self.use_lowercase:
            char_count += 26  # a-z
        if self.use_uppercase:
            char_count += 26  # A-Z
        if self.use_digits:
            char_count += 10  # 0-9
        if self.use_special:
            char_count += 8   # Special chars
            
        # If no options selected, default to lowercase
        if char_count == 0:
            char_count = 26
            
        # Calculate total combinations
        total = 0
        for length in range(self.min_length, self.max_length + 1):
            total += char_count ** length
            
        # If no limit, return the actual total, otherwise apply the default limit
        if self.MAX_PASSWORDS == float('inf'):
            return total
        else:
            return min(total, self.MAX_PASSWORDS)
