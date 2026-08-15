import { useState } from 'react'
import { Upload, FileText, Database, CheckCircle, GitBranch } from 'lucide-react'
import { Button } from '@/components/ui/button.jsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Alert, AlertDescription } from '@/components/ui/alert.jsx'
import PipelineVisualization from './components/PipelineVisualization.jsx'
import './App.css'

// In local dev this falls back to your Flask backend on :5002.
// In production, set VITE_API_URL (e.g. in Vercel/Netlify env vars) to
// your deployed backend's URL, e.g. https://your-backend.onrender.com
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5002'

function App() {
  const [selectedFile, setSelectedFile] = useState(null)
  const [extractedData, setExtractedData] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [processingStatus, setProcessingStatus] = useState('idle')

  const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

  const applySelectedFile = (file) => {
    if (!file) return
    if (file.size > MAX_FILE_SIZE_BYTES) {
      setError('File exceeds the 10MB limit. Please choose a smaller file.')
      setSelectedFile(null)
      setExtractedData(null)
      setProcessingStatus('idle')
      return
    }
    setSelectedFile(file)
    setExtractedData(null)
    setError(null)
    setProcessingStatus('idle')
  }

  const handleFileSelect = (event) => {
    applySelectedFile(event.target.files[0])
  }

  const handleDrop = (event) => {
    event.preventDefault()
    applySelectedFile(event.dataTransfer.files[0])
  }

  const handleDragOver = (event) => {
    event.preventDefault()
  }

  const handleExtract = async () => {
    if (!selectedFile) return

    setIsLoading(true)
    setError(null)
    setProcessingStatus('uploading')

    const formData = new FormData()
    formData.append('file', selectedFile)

    try {
      setProcessingStatus('processing')
      
      const response = await fetch(`${API_URL}/api/extract`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()
      setExtractedData(data)
      setProcessingStatus('complete')
    } catch (err) {
      setError(`Failed to extract data: ${err.message}`)
      setProcessingStatus('error')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <div className="max-w-7xl mx-auto">
        <header className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            Data Extraction Tool
          </h1>
          <p className="text-lg text-gray-600">
            Extract structured data from PDF documents and images using OlmOCR
          </p>
        </header>

        {/* Pipeline Visualization */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <GitBranch className="h-5 w-5" />
              Extraction Pipeline
            </CardTitle>
            <CardDescription>
              Visual representation of the data extraction process
            </CardDescription>
          </CardHeader>
          <CardContent>
            <PipelineVisualization processingStatus={processingStatus} />
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* File Upload Section */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Upload className="h-5 w-5" />
                Upload Document
              </CardTitle>
              <CardDescription>
                Upload a PDF, PNG, or JPG file to extract structured data
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div
                className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-gray-400 transition-colors cursor-pointer"
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onClick={() => document.getElementById('file-input').click()}
              >
                <Upload className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <p className="text-lg font-medium text-gray-700 mb-2">
                  {selectedFile ? selectedFile.name : 'Drop your file here or click to browse'}
                </p>
                <p className="text-sm text-gray-500">
                  Supports PDF, PNG, and JPG files (max 10MB)
                </p>
                <input
                  id="file-input"
                  type="file"
                  accept=".pdf,.png,.jpg,.jpeg"
                  onChange={handleFileSelect}
                  className="hidden"
                />
              </div>

              {selectedFile && (
                <div className="mt-4 p-4 bg-green-50 rounded-lg">
                  <div className="flex items-center gap-2 text-green-700">
                    <CheckCircle className="h-4 w-4" />
                    <span className="font-medium">File selected: {selectedFile.name}</span>
                  </div>
                  <p className="text-sm text-green-600 mt-1">
                    Size: {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
              )}

              <Button
                onClick={handleExtract}
                disabled={!selectedFile || isLoading}
                className="w-full mt-4"
                size="lg"
              >
                {isLoading ? 'Extracting...' : 'Extract Data'}
              </Button>

              {error && (
                <Alert className="mt-4 border-red-200 bg-red-50">
                  <AlertDescription className="text-red-700">
                    {error}
                  </AlertDescription>
                </Alert>
              )}
            </CardContent>
          </Card>

          {/* Extraction Results */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Database className="h-5 w-5" />
                Extracted Data
              </CardTitle>
              <CardDescription>
                Structured data extracted from your document
              </CardDescription>
            </CardHeader>
            <CardContent>
              {extractedData ? (
                <div className="space-y-6">
                  {/* Key Points */}
                  {extractedData.key_points && extractedData.key_points.length > 0 && (
                    <div>
                      <h3 className="font-semibold text-lg mb-3">Key Points</h3>
                      <div className="bg-indigo-50 p-4 rounded-lg">
                        <ul className="space-y-2">
                          {extractedData.key_points.map((point, index) => (
                            <li key={index} className="flex gap-2 text-sm text-gray-700 leading-relaxed">
                              <span className="text-indigo-500 font-bold shrink-0">•</span>
                              <span>{point}</span>
                            </li>
                          ))}
                        </ul>
                        {typeof extractedData.word_count === 'number' && (
                          <p className="text-xs text-gray-400 mt-3">
                            Summarized from {extractedData.word_count.toLocaleString()} words
                          </p>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Entities */}
                  <div>
                    <h3 className="font-semibold text-lg mb-3">Entities</h3>
                    <div className="grid grid-cols-1 gap-4">
                      <div>
                        <h4 className="font-medium text-sm text-gray-600 mb-2">Names</h4>
                        <div className="flex flex-wrap gap-2">
                          {extractedData.entities.names.length > 0 ? (
                            extractedData.entities.names.map((name, index) => (
                              <span key={index} className="px-2 py-1 bg-blue-100 text-blue-800 rounded-md text-sm">
                                {name}
                              </span>
                            ))
                          ) : (
                            <span className="text-gray-400 text-sm">No names found</span>
                          )}
                        </div>
                      </div>

                      <div>
                        <h4 className="font-medium text-sm text-gray-600 mb-2">Dates</h4>
                        <div className="flex flex-wrap gap-2">
                          {extractedData.entities.dates.length > 0 ? (
                            extractedData.entities.dates.map((date, index) => (
                              <span key={index} className="px-2 py-1 bg-green-100 text-green-800 rounded-md text-sm">
                                {date}
                              </span>
                            ))
                          ) : (
                            <span className="text-gray-400 text-sm">No dates found</span>
                          )}
                        </div>
                      </div>

                      <div>
                        <h4 className="font-medium text-sm text-gray-600 mb-2">Addresses</h4>
                        <div className="flex flex-wrap gap-2">
                          {extractedData.entities.addresses.length > 0 ? (
                            extractedData.entities.addresses.map((address, index) => (
                              <span key={index} className="px-2 py-1 bg-purple-100 text-purple-800 rounded-md text-sm">
                                {address}
                              </span>
                            ))
                          ) : (
                            <span className="text-gray-400 text-sm">No addresses found</span>
                          )}
                        </div>
                      </div>

                      <div>
                        <h4 className="font-medium text-sm text-gray-600 mb-2">Emails</h4>
                        <div className="flex flex-wrap gap-2">
                          {extractedData.entities.emails?.length > 0 ? (
                            extractedData.entities.emails.map((email, index) => (
                              <span key={index} className="px-2 py-1 bg-amber-100 text-amber-800 rounded-md text-sm">
                                {email}
                              </span>
                            ))
                          ) : (
                            <span className="text-gray-400 text-sm">No emails found</span>
                          )}
                        </div>
                      </div>

                      <div>
                        <h4 className="font-medium text-sm text-gray-600 mb-2">Phone Numbers</h4>
                        <div className="flex flex-wrap gap-2">
                          {extractedData.entities.phones?.length > 0 ? (
                            extractedData.entities.phones.map((phone, index) => (
                              <span key={index} className="px-2 py-1 bg-rose-100 text-rose-800 rounded-md text-sm">
                                {phone}
                              </span>
                            ))
                          ) : (
                            <span className="text-gray-400 text-sm">No phone numbers found</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Tables */}
                  <div>
                    <h3 className="font-semibold text-lg mb-3">Tables</h3>
                    {extractedData.tables.length > 0 ? (
                      extractedData.tables.map((table, tableIndex) => (
                        <div key={tableIndex} className="mb-4 overflow-x-auto">
                          <table className="w-full border border-gray-200 rounded-lg">
                            <thead className="bg-gray-50">
                              <tr>
                                {table.headers.map((header, headerIndex) => (
                                  <th key={headerIndex} className="px-4 py-2 text-left text-sm font-medium text-gray-700 border-b">
                                    {header}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {table.rows.map((row, rowIndex) => (
                                <tr key={rowIndex} className="hover:bg-gray-50">
                                  {row.map((cell, cellIndex) => (
                                    <td key={cellIndex} className="px-4 py-2 text-sm text-gray-600 border-b">
                                      {cell}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ))
                    ) : (
                      <p className="text-gray-400 text-sm">No tables found</p>
                    )}
                  </div>

                  {/* Raw Text Preview */}
                  <div>
                    <h3 className="font-semibold text-lg mb-3">Raw Text Preview</h3>
                    <div className="bg-gray-50 p-4 rounded-lg max-h-40 overflow-y-auto">
                      <pre className="text-sm text-gray-700 whitespace-pre-wrap">
                        {extractedData.raw_text.substring(0, 500)}
                        {extractedData.raw_text.length > 500 && '...'}
                      </pre>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-12">
                  <FileText className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                  <p className="text-gray-500">
                    Upload and extract a document to see the results here
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

export default App

