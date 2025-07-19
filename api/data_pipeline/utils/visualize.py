import matplotlib.pyplot as plt


def chunks_dist(chunks):
    lengths = [len(ch["content"]) for ch in chunks]
    plt.hist(lengths, bins=50)
    plt.title("Chunk length distribution")
