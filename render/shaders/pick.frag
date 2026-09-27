// pick.frag
// Pick ID çıkışı.
// (Şu an kullanılmıyor — MRT üzerinden pick yapılıyor.)

#version 460 core

in flat uint vPickID;
layout(location = 0) out uint FragColor;

void main() {
    FragColor = vPickID;
}