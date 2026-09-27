// pick.vert
// Sadece pick ID yazmak için basit vertex shader.
// (Şu an kullanılmıyor — MRT üzerinden pick yapılıyor.
//  Gelecekte tek-piksel pick fallback'i için tutuluyor.)

#version 460 core

layout(location = 0) in vec3 aPos;
layout(location = 3) in uint aPickID;

uniform mat4 mvp;

out flat uint vPickID;

void main() {
    gl_Position = mvp * vec4(aPos, 1.0);
    vPickID     = aPickID;
}