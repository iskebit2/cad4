#version 460 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aColor;
layout(location = 3) in uint aPickId;

out vec3 VertexColor;
flat out uint VertexPickId;
uniform mat4 mvp;
uniform float pointSize;

void main() {
    gl_Position = mvp * vec4(aPos, 1.0);
    gl_PointSize = pointSize;
    VertexColor = aColor;
    VertexPickId = aPickId;
}