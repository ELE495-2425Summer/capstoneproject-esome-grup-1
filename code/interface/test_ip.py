# Test scripti - test_udp.py
import socket
import time

def test_udp_discovery():
    message = b"DISCOVER_SERVER"
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(5)
    
    try:
        sock.sendto(message, ('255.255.255.255', 41234))
        print("📡 UDP mesajı gönderildi...")
        
        data, addr = sock.recvfrom(1024)
        print(f"🎯 Cevap alındı: {data.decode()} from {addr}")
        return data.decode().strip()
    except Exception as e:
        print(f"❌ UDP hatası: {e}")
        return None
    finally:
        sock.close()

if __name__ == "__main__":
    test_udp_discovery()