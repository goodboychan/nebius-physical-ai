# G0 드라이런 및 이후 Nebius Jobs 실행용 이미지.
# NGC PyTorch 25.11 (TensorRT 10.14, modelopt 0.37) + 비디오 디코딩용 PyAV.
FROM nvcr.io/nvidia/pytorch:25.11-py3

# torchvision.io의 비디오 읽기는 PyAV를 필요로 하는데 베이스 이미지에 없다.
RUN pip install --no-cache-dir "av==18.1.0"

WORKDIR /workspace
