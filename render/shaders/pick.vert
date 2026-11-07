// pick.vert
#version 460 core

layout(location = 0) in vec3 aPos;
layout(location = 3) in uint aPickID;

uniform mat4 mvp;
uniform float pointSize;

out flat uint vPickID;

void main() {
    gl_Position = mvp * vec4(aPos, 1.0);
    gl_PointSize = pointSize;
    vPickID = aPickID;
}