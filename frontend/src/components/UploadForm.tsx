import React, { useState } from 'react';

const UploadForm: React.FC = () => {
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [clothingOptions, setClothingOptions] = useState<string[]>([]);
    const [errorMessage, setErrorMessage] = useState<string>('');
    
    const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0] || null;
        setSelectedFile(file);
    };

    const handleClothingChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
        const options = Array.from(event.target.selectedOptions).map(option => option.value);
        setClothingOptions(options);
    };

    const handleSubmit = async (event: React.FormEvent) => {
        event.preventDefault();
        if (!selectedFile) {
            setErrorMessage('Please upload an image.');
            return;
        }
        setErrorMessage('');

        const formData = new FormData();
        formData.append('image', selectedFile);
        clothingOptions.forEach(option => formData.append('clothingOptions', option));

        try {
            const response = await fetch('/api/tryon', {
                method: 'POST',
                body: formData,
            });
            if (!response.ok) {
                throw new Error('Failed to generate images');
            }
            // Handle successful response
        } catch (error) {
            setErrorMessage(error.message);
        }
    };

    return (
        <form onSubmit={handleSubmit}>
            <div>
                <label htmlFor="file-upload">Upload Image:</label>
                <input type="file" id="file-upload" accept="image/*" onChange={handleFileChange} />
            </div>
            <div>
                <label htmlFor="clothing-options">Select Clothing Options:</label>
                <select id="clothing-options" multiple onChange={handleClothingChange}>
                    <option value="shirt">Shirt</option>
                    <option value="pants">Pants</option>
                    <option value="dress">Dress</option>
                    <option value="jacket">Jacket</option>
                </select>
            </div>
            {errorMessage && <p style={{ color: 'red' }}>{errorMessage}</p>}
            <button type="submit">Try On</button>
        </form>
    );
};

export default UploadForm;