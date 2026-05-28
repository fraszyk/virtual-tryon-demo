import React from 'react';

interface ResultGalleryProps {
    images: string[];
}

const ResultGallery: React.FC<ResultGalleryProps> = ({ images }) => {
    return (
        <div className="result-gallery">
            {images.length > 0 ? (
                images.map((image, index) => (
                    <div key={index} className="result-item">
                        <img src={image} alt={`Result ${index + 1}`} />
                    </div>
                ))
            ) : (
                <p>No results to display. Please upload an image and select clothing options.</p>
            )}
        </div>
    );
};

export default ResultGallery;