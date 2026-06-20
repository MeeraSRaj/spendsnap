import React, { useState, useEffect } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
  ActivityIndicator,
  FlatList,
  Modal,
  TextInput,
  Alert,
  SafeAreaView,
  StatusBar,
  ScrollView,
  KeyboardAvoidingView,
  Platform
} from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { Ionicons, Feather } from '@expo/vector-icons';

// Interface definitions
interface Expense {
  id: number;
  receipt_id: number | null;
  merchant: string;
  amount: number;
  category: string;
  transaction_date: string;
  created_at: string;
}

const CATEGORIES = [
  { label: '🍴 Food & Dining', value: 'Food & Dining', icon: 'restaurant-outline', color: '#F87171' },
  { label: '🛍️ Shopping', value: 'Shopping', icon: 'bag-handle-outline', color: '#FB923C' },
  { label: '⛽ Fuel', value: 'Fuel', icon: 'car-outline', color: '#FBBF24' },
  { label: '💻 Electronics', value: 'Electronics', icon: 'hardware-chip-outline', color: '#60A5FA' },
  { label: '🎬 Entertainment', value: 'Entertainment', icon: 'film-outline', color: '#C084FC' },
  { label: '🔌 Utilities', value: 'Utilities', icon: 'flash-outline', color: '#34D399' },
  { label: '🏫 Canteen', value: 'Canteen', icon: 'cafe-outline', color: '#2DD4BF' },
  { label: '❓ Uncategorized', value: 'Uncategorized', icon: 'help-circle-outline', color: '#94A3B8' },
];

export default function App() {
  // State variables
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState('');
  const [apiBaseUrl, setApiBaseUrl] = useState('http://localhost:8000'); // Configurable for real device testing
  const [showSettings, setShowSettings] = useState(false);
  const [tempApiUrl, setTempApiUrl] = useState('http://localhost:8000');

  // Edit/Correction Modal State
  const [selectedExpense, setSelectedExpense] = useState<Expense | null>(null);
  const [editMerchant, setEditMerchant] = useState('');
  const [editAmount, setEditAmount] = useState('');
  const [editCategory, setEditCategory] = useState('Uncategorized');
  const [showCorrectionModal, setShowCorrectionModal] = useState(false);

  // Load expenses on mount
  useEffect(() => {
    fetchExpenses();
  }, [apiBaseUrl]);

  // Fetch all expenses from backend
  const fetchExpenses = async () => {
    try {
      const response = await fetch(`${apiBaseUrl}/api/expenses`);
      if (response.ok) {
        const data = await response.json();
        setExpenses(data);
      } else {
        console.warn('Failed to fetch expenses: status', response.status);
      }
    } catch (error) {
      console.error('Error fetching expenses:', error);
    }
  };

  // Setup permissions
  const requestPermissions = async () => {
    if (Platform.OS !== 'web') {
      const libraryStatus = await ImagePicker.requestMediaLibraryPermissionsAsync();
      const cameraStatus = await ImagePicker.requestCameraPermissionsAsync();
      
      if (libraryStatus.status !== 'granted' || cameraStatus.status !== 'granted') {
        Alert.alert(
          'Permissions Required',
          'Sorry, we need camera and library roll permissions to capture and read receipts!'
        );
        return false;
      }
      return true;
    }
    return true;
  };

  // Handle image capture / selection
  const handleSelectImage = async (useCamera: boolean) => {
    const hasPermission = await requestPermissions();
    if (!hasPermission) return;

    let result;
    const options: ImagePicker.ImagePickerOptions = {
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      quality: 0.8,
    };

    if (useCamera) {
      result = await ImagePicker.launchCameraAsync(options);
    } else {
      result = await ImagePicker.launchImageLibraryAsync(options);
    }

    if (!result.canceled && result.assets && result.assets.length > 0) {
      uploadReceipt(result.assets[0].uri);
    }
  };

  // Upload receipt image to FastAPI backend
  const uploadReceipt = async (imageUri: string) => {
    setLoading(true);
    setUploadStatus('Uploading image...');

    // Extract filename and mime type
    const filename = imageUri.split('/').pop() || 'receipt.jpg';
    const match = /\.(\w+)$/.exec(filename);
    const type = match ? `image/${match[1]}` : `image/jpeg`;

    const formData = new FormData();
    // In React Native, we pass an object matching the file structure for multipart/form-data
    formData.append('file', {
      uri: imageUri,
      name: filename,
      type,
    } as any);

    try {
      setUploadStatus('Running OCR text extraction...');
      const response = await fetch(`${apiBaseUrl}/api/upload`, {
        method: 'POST',
        body: formData,
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      if (!response.ok) {
        const errorDetail = await response.text();
        throw new Error(errorDetail || 'Server upload failed');
      }

      setUploadStatus('Parsing receipt details...');
      const result = await response.json();
      
      // Auto-trigger Verification & Correction screen with extracted details
      openCorrectionModal(result.expense);
      fetchExpenses(); // Refresh feed in background
    } catch (error: any) {
      Alert.alert('Upload Failed', error.message || 'Could not connect to backend server. Make sure the API URL is correct.');
      console.error(error);
    } finally {
      setLoading(false);
      setUploadStatus('');
    }
  };

  // Open correction modal for an expense
  const openCorrectionModal = (expense: Expense) => {
    setSelectedExpense(expense);
    setEditMerchant(expense.merchant);
    setEditAmount(expense.amount.toString());
    setEditCategory(expense.category || 'Uncategorized');
    setShowCorrectionModal(true);
  };

  // Save the corrected details to the backend
  const handleSaveCorrection = async () => {
    if (!selectedExpense) return;
    if (!editMerchant.trim()) {
      Alert.alert('Validation Error', 'Merchant name cannot be empty.');
      return;
    }
    const parsedAmount = parseFloat(editAmount);
    if (isNaN(parsedAmount) || parsedAmount < 0) {
      Alert.alert('Validation Error', 'Please enter a valid numeric amount.');
      return;
    }

    try {
      setLoading(true);
      const response = await fetch(`${apiBaseUrl}/api/expenses/${selectedExpense.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          merchant: editMerchant,
          amount: parsedAmount,
          category: editCategory,
        }),
      });

      if (response.ok) {
        setShowCorrectionModal(false);
        setSelectedExpense(null);
        fetchExpenses(); // Refresh feed
      } else {
        const err = await response.text();
        Alert.alert('Update Failed', err || 'Could not update expense.');
      }
    } catch (error) {
      Alert.alert('Error', 'Connection error while saving corrections.');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  // Delete an expense
  const handleDeleteExpense = async (id: number) => {
    Alert.alert(
      'Delete Expense',
      'Are you sure you want to delete this expense and its receipt?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              const response = await fetch(`${apiBaseUrl}/api/expenses/${id}`, {
                method: 'DELETE',
              });
              if (response.ok) {
                fetchExpenses();
                if (selectedExpense && selectedExpense.id === id) {
                  setShowCorrectionModal(false);
                  setSelectedExpense(null);
                }
              } else {
                Alert.alert('Error', 'Failed to delete expense.');
              }
            } catch (error) {
              Alert.alert('Error', 'Connection error while deleting.');
              console.error(error);
            }
          },
        },
      ]
    );
  };

  // Helper to format date
  const formatDate = (dateStr: string) => {
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('en-IN', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch (e) {
      return dateStr;
    }
  };

  // Helper to find category metadata
  const getCategoryMeta = (val: string) => {
    return CATEGORIES.find(c => c.value === val) || CATEGORIES[CATEGORIES.length - 1];
  };

  // Calculate total monthly spending
  const totalSpending = expenses.reduce((acc, curr) => acc + curr.amount, 0);

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="light-content" backgroundColor="#0F172A" />
      
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.logoText}>💸 SpendSnap AI</Text>
          <Text style={styles.subtitleText}>Your Financial Memory</Text>
        </View>
        <TouchableOpacity 
          style={styles.settingsButton}
          onPress={() => {
            setTempApiUrl(apiBaseUrl);
            setShowSettings(!showSettings);
          }}
        >
          <Feather name="settings" size={22} color="#94A3B8" />
        </TouchableOpacity>
      </View>

      {/* Settings Panel */}
      {showSettings && (
        <View style={styles.settingsPanel}>
          <Text style={styles.settingsTitle}>API Base Configuration</Text>
          <Text style={styles.settingsLabel}>FastAPI Server URL:</Text>
          <View style={styles.settingsRow}>
            <TextInput
              style={styles.settingsInput}
              value={tempApiUrl}
              onChangeText={setTempApiUrl}
              placeholder="e.g., http://192.168.1.100:8000"
              placeholderTextColor="#475569"
              autoCapitalize="none"
              autoCorrect={false}
            />
            <TouchableOpacity 
              style={styles.saveSettingsButton}
              onPress={() => {
                setApiBaseUrl(tempApiUrl);
                setShowSettings(false);
                Alert.alert('Configuration Saved', `Targeting backend: ${tempApiUrl}`);
              }}
            >
              <Text style={styles.saveSettingsText}>Save</Text>
            </TouchableOpacity>
          </View>
          <Text style={styles.settingsHelp}>
            Note: Use localhost/10.0.2.2 for Android emulator, or your computer's local network IP for physical devices.
          </Text>
        </View>
      )}

      {/* Total Spend Banner */}
      <View style={styles.summaryCard}>
        <Text style={styles.summaryLabel}>TOTAL MEMORIZED SPEND</Text>
        <Text style={styles.summaryValue}>₹{totalSpending.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</Text>
        <Text style={styles.summaryCount}>{expenses.length} transaction{expenses.length !== 1 ? 's' : ''} stored</Text>
      </View>

      {/* Action Buttons */}
      <View style={styles.actionRow}>
        <TouchableOpacity style={styles.captureButton} onPress={() => handleSelectImage(true)}>
          <Ionicons name="camera" size={24} color="#0F172A" />
          <Text style={styles.captureButtonText}>Snap Receipt</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.pickerButton} onPress={() => handleSelectImage(false)}>
          <Ionicons name="image" size={24} color="#38BDF8" />
          <Text style={styles.pickerButtonText}>Upload Image</Text>
        </TouchableOpacity>
      </View>

      {/* Expense List */}
      <View style={styles.listContainer}>
        <Text style={styles.listHeader}>Memorized History</Text>
        
        {expenses.length === 0 ? (
          <View style={styles.emptyContainer}>
            <Feather name="cloud-rain" size={48} color="#475569" />
            <Text style={styles.emptyText}>No financial memory stored yet.</Text>
            <Text style={styles.emptySubtext}>Capture a receipt to start parsing details automatically.</Text>
          </View>
        ) : (
          <FlatList
            data={expenses}
            keyExtractor={(item) => item.id.toString()}
            contentContainerStyle={styles.listContent}
            renderItem={({ item }) => {
              const meta = getCategoryMeta(item.category);
              return (
                <TouchableOpacity 
                  style={styles.expenseCard}
                  onPress={() => openCorrectionModal(item)}
                  activeOpacity={0.8}
                >
                  <View style={[styles.categoryCircle, { backgroundColor: `${meta.color}20` }]}>
                    <Ionicons name={meta.icon as any} size={22} color={meta.color} />
                  </View>
                  <View style={styles.expenseInfo}>
                    <Text style={styles.merchantText} numberOfLines={1}>{item.merchant}</Text>
                    <Text style={styles.dateText}>{formatDate(item.transaction_date)}</Text>
                  </View>
                  <View style={styles.expenseAmountCol}>
                    <Text style={styles.amountText}>₹{item.amount.toFixed(2)}</Text>
                    <Text style={styles.categoryLabel}>{meta.value}</Text>
                  </View>
                  <TouchableOpacity 
                    style={styles.deleteButton}
                    onPress={() => handleDeleteExpense(item.id)}
                  >
                    <Ionicons name="trash-outline" size={18} color="#EF4444" />
                  </TouchableOpacity>
                </TouchableOpacity>
              );
            }}
          />
        )}
      </View>

      {/* Loading Overlay Modal */}
      <Modal visible={loading && !!uploadStatus} transparent animationType="fade">
        <View style={styles.overlayContainer}>
          <View style={styles.loaderBox}>
            <ActivityIndicator size="large" color="#38BDF8" />
            <Text style={styles.loaderTitle}>SpendSnap OCR</Text>
            <Text style={styles.loaderStatus}>{uploadStatus}</Text>
          </View>
        </View>
      </Modal>

      {/* Verification & Correction Modal */}
      <Modal visible={showCorrectionModal} transparent animationType="slide">
        <KeyboardAvoidingView 
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.correctionOverlay}
        >
          <View style={styles.correctionBox}>
            <View style={styles.correctionHeader}>
              <Text style={styles.correctionTitle}>Verify & Correct Details</Text>
              <TouchableOpacity onPress={() => setShowCorrectionModal(false)}>
                <Ionicons name="close" size={24} color="#94A3B8" />
              </TouchableOpacity>
            </View>

            <ScrollView contentContainerStyle={styles.correctionScroll}>
              {/* Merchant Input */}
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Merchant / Store Name</Text>
                <TextInput
                  style={styles.inputField}
                  value={editMerchant}
                  onChangeText={setEditMerchant}
                  placeholder="Enter merchant name"
                  placeholderTextColor="#475569"
                />
              </View>

              {/* Amount Input */}
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Total Amount (₹)</Text>
                <TextInput
                  style={styles.inputField}
                  value={editAmount}
                  onChangeText={setEditAmount}
                  placeholder="Enter amount"
                  placeholderTextColor="#475569"
                  keyboardType="numeric"
                />
              </View>

              {/* Category Dropdown (Custom Grid List Selector) */}
              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Assign Category</Text>
                <View style={styles.categoryGrid}>
                  {CATEGORIES.map((cat) => {
                    const isSelected = editCategory === cat.value;
                    return (
                      <TouchableOpacity
                        key={cat.value}
                        style={[
                          styles.gridCategoryBtn,
                          isSelected && { backgroundColor: `${cat.color}30`, borderColor: cat.color }
                        ]}
                        onPress={() => setEditCategory(cat.value)}
                      >
                        <Text style={[styles.gridCategoryText, isSelected && { color: cat.color }]}>
                          {cat.label.split(' ')[0]} {cat.value}
                        </Text>
                      </TouchableOpacity>
                    );
                  })}
                </View>
              </View>
            </ScrollView>

            {/* Actions */}
            <View style={styles.correctionActions}>
              {selectedExpense && (
                <TouchableOpacity 
                  style={styles.discardBtn}
                  onPress={() => handleDeleteExpense(selectedExpense.id)}
                >
                  <Text style={styles.discardBtnText}>Delete</Text>
                </TouchableOpacity>
              )}
              <TouchableOpacity style={styles.saveBtn} onPress={handleSaveCorrection}>
                <Text style={styles.saveBtnText}>Save & Lock in Memory</Text>
              </TouchableOpacity>
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}

// CSS Stylesheet
const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#0F172A',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingTop: 15,
    paddingBottom: 10,
    backgroundColor: '#0F172A',
    borderBottomWidth: 1,
    borderBottomColor: '#1E293B',
  },
  logoText: {
    fontSize: 22,
    fontWeight: '800',
    color: '#38BDF8',
    letterSpacing: 0.5,
  },
  subtitleText: {
    fontSize: 12,
    color: '#94A3B8',
    marginTop: 2,
  },
  settingsButton: {
    padding: 8,
    borderRadius: 8,
    backgroundColor: '#1E293B',
  },
  settingsPanel: {
    padding: 15,
    marginHorizontal: 20,
    marginTop: 10,
    backgroundColor: '#1E293B',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#334155',
  },
  settingsTitle: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#F8FAFC',
    marginBottom: 10,
  },
  settingsLabel: {
    fontSize: 12,
    color: '#94A3B8',
    marginBottom: 5,
  },
  settingsRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  settingsInput: {
    flex: 1,
    height: 40,
    backgroundColor: '#0F172A',
    borderRadius: 8,
    paddingHorizontal: 10,
    color: '#F8FAFC',
    borderWidth: 1,
    borderColor: '#475569',
  },
  saveSettingsButton: {
    marginLeft: 10,
    paddingHorizontal: 15,
    height: 40,
    backgroundColor: '#38BDF8',
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
  },
  saveSettingsText: {
    color: '#0F172A',
    fontWeight: 'bold',
    fontSize: 14,
  },
  settingsHelp: {
    fontSize: 10,
    color: '#64748B',
    marginTop: 6,
  },
  summaryCard: {
    margin: 20,
    padding: 20,
    borderRadius: 16,
    backgroundColor: '#1E293B',
    borderWidth: 1,
    borderColor: '#334155',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 5,
    elevation: 6,
  },
  summaryLabel: {
    fontSize: 11,
    fontWeight: '800',
    color: '#38BDF8',
    letterSpacing: 1.5,
    marginBottom: 5,
  },
  summaryValue: {
    fontSize: 32,
    fontWeight: '900',
    color: '#F8FAFC',
    letterSpacing: 0.5,
  },
  summaryCount: {
    fontSize: 12,
    color: '#94A3B8',
    marginTop: 5,
  },
  actionRow: {
    flexDirection: 'row',
    paddingHorizontal: 20,
    justifyContent: 'space-between',
    marginBottom: 15,
  },
  captureButton: {
    flex: 1,
    flexDirection: 'row',
    backgroundColor: '#38BDF8',
    paddingVertical: 14,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 8,
    shadowColor: '#38BDF8',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
    elevation: 3,
  },
  captureButtonText: {
    color: '#0F172A',
    fontWeight: 'bold',
    fontSize: 16,
    marginLeft: 8,
  },
  pickerButton: {
    flex: 1,
    flexDirection: 'row',
    backgroundColor: '#1E293B',
    borderWidth: 1.5,
    borderColor: '#38BDF8',
    paddingVertical: 14,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
    marginLeft: 8,
  },
  pickerButtonText: {
    color: '#38BDF8',
    fontWeight: 'bold',
    fontSize: 16,
    marginLeft: 8,
  },
  listContainer: {
    flex: 1,
    backgroundColor: '#0F172A',
    paddingHorizontal: 20,
  },
  listHeader: {
    fontSize: 18,
    fontWeight: '700',
    color: '#F8FAFC',
    marginBottom: 10,
  },
  listContent: {
    paddingBottom: 20,
  },
  expenseCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1E293B',
    padding: 14,
    borderRadius: 12,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#334155',
  },
  categoryCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  expenseInfo: {
    flex: 1,
    justifyContent: 'center',
  },
  merchantText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#F8FAFC',
    marginBottom: 2,
  },
  dateText: {
    fontSize: 11,
    color: '#64748B',
  },
  expenseAmountCol: {
    alignItems: 'flex-end',
    justifyContent: 'center',
    marginRight: 8,
  },
  amountText: {
    fontSize: 16,
    fontWeight: '800',
    color: '#F8FAFC',
  },
  categoryLabel: {
    fontSize: 10,
    color: '#94A3B8',
    marginTop: 2,
  },
  deleteButton: {
    padding: 8,
    justifyContent: 'center',
    alignItems: 'center',
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingTop: 40,
  },
  emptyText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#64748B',
    marginTop: 15,
  },
  emptySubtext: {
    fontSize: 12,
    color: '#475569',
    textAlign: 'center',
    marginTop: 5,
    maxWidth: '80%',
  },
  overlayContainer: {
    flex: 1,
    backgroundColor: 'rgba(15, 23, 42, 0.85)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  loaderBox: {
    backgroundColor: '#1E293B',
    padding: 30,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#334155',
    alignItems: 'center',
    width: '80%',
  },
  loaderTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#F8FAFC',
    marginTop: 15,
  },
  loaderStatus: {
    fontSize: 12,
    color: '#94A3B8',
    marginTop: 8,
    textAlign: 'center',
  },
  correctionOverlay: {
    flex: 1,
    backgroundColor: 'rgba(15, 23, 42, 0.75)',
    justifyContent: 'flex-end',
  },
  correctionBox: {
    backgroundColor: '#1E293B',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    paddingTop: 20,
    paddingBottom: Platform.OS === 'ios' ? 40 : 25,
    maxHeight: '85%',
    borderWidth: 1,
    borderColor: '#334155',
  },
  correctionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingBottom: 15,
    borderBottomWidth: 1,
    borderBottomColor: '#334155',
  },
  correctionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#F8FAFC',
  },
  correctionScroll: {
    padding: 20,
  },
  inputGroup: {
    marginBottom: 16,
  },
  inputLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: '#38BDF8',
    marginBottom: 8,
    letterSpacing: 0.5,
  },
  inputField: {
    height: 48,
    backgroundColor: '#0F172A',
    borderRadius: 8,
    paddingHorizontal: 14,
    color: '#F8FAFC',
    fontSize: 16,
    borderWidth: 1,
    borderColor: '#475569',
  },
  categoryGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginHorizontal: -4,
  },
  gridCategoryBtn: {
    backgroundColor: '#0F172A',
    borderWidth: 1,
    borderColor: '#334155',
    borderRadius: 8,
    paddingVertical: 10,
    paddingHorizontal: 12,
    margin: 4,
  },
  gridCategoryText: {
    color: '#94A3B8',
    fontSize: 12,
    fontWeight: 'bold',
  },
  correctionActions: {
    flexDirection: 'row',
    paddingHorizontal: 20,
    paddingTop: 10,
  },
  discardBtn: {
    flex: 1,
    backgroundColor: '#EF444420',
    borderWidth: 1,
    borderColor: '#EF4444',
    height: 48,
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 10,
  },
  discardBtnText: {
    color: '#EF4444',
    fontWeight: 'bold',
    fontSize: 16,
  },
  saveBtn: {
    flex: 2,
    backgroundColor: '#38BDF8',
    height: 48,
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
  },
  saveBtnText: {
    color: '#0F172A',
    fontWeight: 'bold',
    fontSize: 16,
  },
});
