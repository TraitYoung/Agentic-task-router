def is_prime(n):
    """判断一个数是否为质数"""
    if n < 2:
        return False
    if n == 2:
        return True
    if n % 2 == 0:
        return False
    # 只需检查到 sqrt(n)
    for i in range(3, int(n**0.5) + 1, 2):
        if n % i == 0:
            return False
    return True


# 生成1-100的所有质数
primes = []
for n in range(1, 101):
    if is_prime(n):
        primes.append(n)

print("1~100的所有质数：")
print(primes)
print(f"共 {len(primes)} 个质数")
