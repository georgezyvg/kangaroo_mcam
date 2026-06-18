import os
import time
import random
import gmpy2
from multiprocessing import Pool, cpu_count

# Elliptic Curve secp256k1 Parameters
modulo = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
order = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
Gx = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
Gy = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8


class Point:
    def __init__(self, x=0, y=0):
        self.x = x
        self.y = y


PG = Point(Gx, Gy)
Z = Point(0, 0)  # zero-point, infinite in real x,y-plane


def egcd(a, b):
    if a == 0:
        return (b, 0, 1)
    else:
        g, x, y = egcd(b % a, a)
        return (g, y - (b // a) * x, x)


def rev(b, n=modulo):
    while b < 0:
        b += modulo
    g, x, _ = egcd(b, n)
    if g == 1:
        return x % n


def mul2(P, p=modulo):
    R = Point()
    c = 3 * P.x * P.x * rev(2 * P.y, p) % p
    R.x = (c * c - 2 * P.x) % p
    R.y = (c * (P.x - R.x) - P.y) % p
    return R


def add(P, Q, p=modulo):
    R = Point()
    dx = Q.x - P.x
    dy = Q.y - P.y
    c = dy * gmpy2.invert(dx, p) % p
    R.x = (c * c - P.x - Q.x) % p
    R.y = (c * (P.x - R.x) - P.y) % p
    return R


def mulk(k, P=PG, p=modulo):
    if k == 0:
        return Z
    elif k == 1:
        return P
    elif k % 2 == 0:
        return mulk(k // 2, mul2(P, p), p)
    else:
        return add(P, mulk((k - 1) // 2, mul2(P, p), p), p)


def X2Y(X, p=modulo):
    if p % 4 != 3:
        print("Prime must be 3 modulo 4")
        return 0
    Y = pow(X ** 3 + 7, (p + 1) // 4, p)
    return Y


def comparator(starttime):
    A, Ak, B, Bk = [], [], [], []
    with open("tame.txt") as f:
        for line in f:
            L = line.split()
            a = int(L[0], 16)
            b = int(L[1])
            A.append(a)
            Ak.append(b)
    with open("wild.txt") as f:
        for line in f:
            L = line.split()
            a = int(L[0], 16)
            b = int(L[1])
            B.append(a)
            Bk.append(b)
    result = list(set(A) & set(B))
    if len(result) > 0:
        sol_kt = A.index(result[0])
        sol_kw = B.index(result[0])
        print("Total time: %.2f sec" % (time.time() - starttime))
        d = Ak[sol_kt] - Bk[sol_kw]
        print("SOLVED:", d)
        with open("results.txt", "a") as file:
            file.write(("%d" % (Ak[sol_kt] - Bk[sol_kw])) + "\n")
            file.write("---------------\n")
        return True
    else:
        return False

def check(P, Pindex, DP_rarity, file2save, starttime):
    if P.x % DP_rarity == 0:
        with open(file2save, "a") as file:
            file.write(("%064x %d" % (P.x, Pindex)) + "\n")
        return comparator(starttime)
    else:
        return False

def parallel_search(args):
    Nt, Nw, DP_rarity, hop_modulo, P, W0, problem, starttime, subrange_start, subrange_end = args
    T, t, dt = [], [], []
    W, w, dw = [], [], []
    subrange_size = subrange_end - subrange_start + 1

    # Tame Walk Initialization
    for k in range(Nt):
        t.append(subrange_start + random.randint(0, subrange_size - 1))
        T.append(mulk(t[k]))
        dt.append(0)

    # Wild Walk Initialization
    for k in range(Nw):
        w.append(subrange_start + random.randint(0, subrange_size - 1))
        W.append(add(W0, mulk(w[k])))
        dw.append(0)

    Hops = 0
    solved = False
    t0 = time.time()  # For measuring h/s
    Hops_old = 0

    while not solved:
        for k in range(Nt):
            Hops += 1
            pw = T[k].x % hop_modulo
            dt[k] = 1 << pw
            if check(T[k], t[k], DP_rarity, "tame.txt", starttime):
                solved = True
                break
            t[k] += dt[k]
            T[k] = add(P[pw], T[k])
        if solved:
            break

        for k in range(Nw):
            Hops += 1
            pw = W[k].x % hop_modulo
            dw[k] = 1 << pw
            if check(W[k], w[k], DP_rarity, "wild.txt", starttime):
                solved = True
                break
            w[k] += dw[k]
            W[k] = add(P[pw], W[k])
        if solved:
            break

        # Periodically log hops per second
        t1 = time.time()
        if (t1 - t0) > 5:  # Print every 5 seconds
            hps = (Hops - Hops_old) / (t1 - t0)
            print(f"Process {os.getpid()} h/s: {hps:.3f}")
            t0 = t1
            Hops_old = Hops

    return Hops


def main():
    global PG, W0, kangoo_power, Nt, Nw, problem
    problems = [
        ("029d8c5d35231d75eb87fd2c5f05f65281ed9573dc41853288c62ee94eb2590b7a", 16),
        ("02e0a8b039282faf6fe0fd769cfbc4b6b4cf8758ba68220eac420e32b91ddfa673", 160),
        ("036ea839d22847ee1dce3bfc5b11f6cf785b0682db58c35b63d1342eb221c3490c", 24),
        ("0209c58240e50e3ba3f833c82655e8725c037a2294e14cf5d73a5df8d56159de69", 32),
    ]

    problem = 135
    for elem in problems:
        s, n = elem
        if problem == n:
            break

    kangoo_power = 3
    Nt = Nw = 2**kangoo_power
    X = int(s, 16)
    Y = X2Y(X % (2**256))
    if Y % 2 != (X >> 256) % 2:
        Y = modulo - Y
    W0 = Point(X % (2**256), Y)

    # Precompute the P table (elliptic curve points)
    P = [PG]
    for k in range(255):
        P.append(mul2(P[k]))
    print("P-table prepared")

    DP_rarity = 1 << ((problem - 2 * kangoo_power) // 2 - 2)
    hop_modulo = ((problem - 1) // 2) + kangoo_power
    starttime = time.time()

    # Divide the bit range among threads
    num_cores = cpu_count()
    full_range = 2 ** (problem - 1)
    subrange_size = full_range // num_cores
    args_list = [
        (
            Nt, Nw, DP_rarity, hop_modulo, P, W0, problem, starttime,
            i * subrange_size, (i + 1) * subrange_size - 1
        )
        for i in range(num_cores)
    ]

    # Use Pool for parallel processing
    with Pool(processes=num_cores) as pool:
        results = pool.map(parallel_search, args_list)

    total_hops = sum(results)
    average_hops = total_hops / num_cores
    print(f"Total hops: {total_hops}")
    print(f"Average hops per process: {average_hops}")
    print(f"Total time: {time.time() - starttime:.2f} seconds")


if __name__ == "__main__":
    main()
