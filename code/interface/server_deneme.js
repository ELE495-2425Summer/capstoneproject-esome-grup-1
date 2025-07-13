//// GEREKLI MODULLERI YUKLEME VE SERVER ACMA /////////////////////////////////////////////////////////////////////////////////////////////////////////////

const express = require('express');      /* "Express" web sunucusu olusturmak amaciyla 
                                            Node.js icin yazilmis bir kutuphane */ 

const { Server } = require('socket.io'); /* real-time,cift-yonlu iletisim icin, 
                                            socket.io modulunden sadece "Server" class'i aliniyor
                                            -> "Socket.io" web sayfasi ile sunucu arasinda real-time
                                            bir iletisim icin kulanilan bir modul
                                            KISACASI bir socket.io server'i olusturduk */

const http = require('http');            /* express uygulamasini HTTP sunucusuna sarmak icin 
                                            Node.js'nin built-in HTTP modulunu yukluyor, bu modul ile
                                            bir "web sunucusu" olusturabiliyoruz */

const path = require('path');            // dosya yollarini platforma gore duzgun olusturmak icin Node.js'in built-in modulu

const app = express(); /* burada bir "web uygulamasi objesi" olusturuyoruz, bu obje web uygulamasinin temeli,
                          yine bu obje ile HTTP isteklerini kontrol edebiliyoruz ve
                          Express'in tum ozelliklerini bu obje uzerinden kullanabiliyoruz */

const server = http.createServer(app); /* 
                                        burada HTTP sunucusunu olusturuyoruz, parametre olarak "app" verdigimiz
                                        icin gelen HTTP istekleri Express uygulamasi tarafindan islenecek
                                        yani "server" degiskeni hem HTTP sunucusunu hem de Express uygulamasini 
                                        barindiran bir nesne */

const io = new Server(server);          /* bu satir ile eksta port acmamiza gerek kalmiyor, Socket.IO'yu zaten var 
                                           olan HTTP sunucusuna entegre etmis oluyoruz, boylece hem normal HTTP istekleri 
                                           (web sayfasi yuklemek gibi) hem de WebSocket baglantilari (gercek zamanli veri 
                                           icin) ayni port ve ayni sunucu uzerinden calisiyor.
                                           -> WebSocket:  web tarayicisi ile sunucu arasinda surekli acik kalan ve 
                                           cift yonlu gercek zamanli veri aktarimi saglayan iletisim kanali.
                                           "server" sayesinde web sayfasi istekleri ile Socket.IO real-time baglantilari
                                           ayni port ve ayni server uzerinden yurutuluyor */


//// STATIK DOSYALARI SUN ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

app.use(express.static(__dirname));     // klasordeki html, js gibi dosyalari dogrudan web tarayicisina servis ediliyor

app.get('/', (req, res) => {                               
  res.sendFile(path.join(__dirname, 'index_deneme.html'));
});
/* '/': HTTP GET, biri sunucunun ana sayfasine gittiginde kod calisir
   'req': gelen istek
   'res': yanit
   'sendFile()': client'a(istemci) dosya gonderir
   'path.join()': klasor yoluna parametre olarak verilen dosyayi ekler ve tam file path'i olusturur */


//// Socket.IO BAGLANTISI ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

/* io.on () {} kod parcasinda yeni bir istemci(orn. web tarayicisi) server'a baglandiginda yapilacaklar tanimlaniyor,
   bir tarayici sunucuya baglandiginda "connection" olayi tetikleniyor
   -> socket: server ile baglati kuran ve her bir istemciye ozel acilan bir iletisim kanalidir, tarayici server'a 
   baglandiginda server bu baglantiya ozel bir socket nesnesi olusturur ve bu socket uzerinden SADECE o istemci ile
   iletisim kurulur */

io.on('connection', (socket) => {
  console.log('Yeni istemci bağlı:', socket.id); /* yeni bir istemci(tarayici) baglandiginda terminale sunu yazar: 
                                                    'Yeni istemci bağlı: <istemci_id>'
                                                    "socket.id" bu baglantiya ozel olusturulan essiz bir ID */ 
  
  console.log('veri_guncelle event listener kuruldu'); /* bilgi amacli log, konsola "veri_guncelle event listener kuruldu" yazar 
                                                          bir sonraki satirdaki "veri_guncelle" olayini dinlemeye basladigini gosteriyor */


  /* bu kod parcasi istemciden 'veri_guncelle' adinda bir olay 
  geldiginde calisir ve input olarak "data" objesini alir */
  socket.on('veri_guncelle', (data) => {
    console.log('Gelen veri:', data); // gelen veriyi terminale yazar
    io.emit('veri_guncelle', data);   // gelen veriyi server'a bagli tum istemcilere yayinlar
  });

  /* bu kod parcasi istemciden 'arac_durumu_guncelle' adinda bir olay 
  geldiginde calisir ve input olarak "data" objesini alir */
  socket.on('arac_durumu_guncelle', (data) => {
    console.log('Gelen arac durumu', data); // gelen veriyi terminale yazar
    io.emit('arac_durumu_guncelle', data);   // gelen veriyi server'a bagli tum istemcilere yayinlar
  });

  /* bu kod parcasi istemciden 'log' adinda bir mesaj 
  geldiginde calisir ve input olarak "msg" objesini alir */
  socket.on('log', (msg) => {
    console.log('Gelen log:', msg);   // gelen veriyi terminale yazar
    io.emit('log', msg);              // gelen veriyi server'a bagli tum istemcilere yayinlar
  });
  
  /* bu kod parcasi istemciden 'arac_kontrol' adinda bir olay 
  geldiginde calisir ve input olarak "data" objesini alir */
  socket.on('arac_kontrol', (data) => {
    console.log('Araç kontrol komutu:', data); // gelen veriyi terminale yazar
    io.emit('arac_kontrol', data);             // gelen veriyi server'a bagli tum istemcilere yayinlar
  });
});


//// SUNUCUYU BASLAT ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

// sunucu 3000 numarali portta baslatilir
server.listen(3000, () => {
  console.log('Sunucu çalışıyor: http://localhost:3000');
});

// web sayfasi otomatik acilir
const { exec } = require('child_process');
exec('start http://localhost:3000');

// web sayfasi kapandiginda sunucuyu kapatmak icin calisan kod parcasi:
app.post('/kapat', (req, res) => {
  console.log('Web arayüzü kapatıldı, sunucu kapanıyor...');
  res.sendStatus(200); // istemciye OK dön

  // Küçük gecikmeyle process'i kapat
  setTimeout(() => {
    process.exit(0);
  }, 500);
});


